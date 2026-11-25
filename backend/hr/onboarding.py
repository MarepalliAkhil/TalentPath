"""One-click hire to onboard.

`hire(offer, actor)` runs in a single transaction: the application moves to
Hired, an employee record is created, the same login becomes an employee
(audited), leave balances are credited and prorated, the checklist and the
first-week plan are generated, a buddy is chosen, other open applications are
withdrawn politely and the job's openings count goes down (the job closes when
filled). If any step fails, nothing is saved.
"""

from datetime import date, time, timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import Role, User
from accounts.services import revoke_sessions
from applications.models import ApplicationEvent
from applications.models import ApplicationStatus as S
from core.audit import audit
from interviews.timeutil import today_ist
from jobs.models import JobStatus
from notifications.services import notify
from org.models import Department, Location

from . import leave as leave_engine
from .calendar_rules import add_working_days
from .models import (
    Employee,
    EmployeeStatus,
    FirstWeekSession,
    OnboardingTask,
    OnboardingTemplateItem,
    TaskOwner,
)

BUDDY_MIN_MONTHS = 6
CODE_PREFIX = "LW"


def months_before(day: date, months: int) -> date:
    year, month = divmod(day.year * 12 + day.month - 1 - months, 12)
    month += 1
    last = (date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)).day
    return date(year, month, min(day.day, last))


def next_code() -> str:
    numbers = [
        int(code[len(CODE_PREFIX) :])
        for code in Employee.objects.filter(code__startswith=CODE_PREFIX).values_list("code", flat=True)
        if code[len(CODE_PREFIX) :].isdigit()
    ]
    return f"{CODE_PREFIX}{(max(numbers) + 1) if numbers else 1001}"


def ensure_employee(user, *, department, location, designation="", joined_on=None, manager=None) -> Employee:
    """Staff who predate week 3B get a record the first time one is needed."""
    existing = Employee.objects.filter(user=user).first()
    if existing:
        return existing
    return Employee.objects.create(
        user=user,
        code=next_code(),
        designation=designation or user.get_role_display(),
        department=department,
        location=location,
        manager=manager,
        joined_on=joined_on or today_ist(timezone.now()) - timedelta(days=400),
    )


def choose_buddy(department, joining: date, *, exclude_ids=()) -> Employee | None:
    """Same department, joined at least six months before, fewest current buddies.
    Never the reporting manager or the joiner (pass them in exclude_ids). Ties go to the
    most recent joiner (closest to the new person's experience), then the employee code."""
    cutoff = months_before(joining, BUDDY_MIN_MONTHS)
    return (
        Employee.objects.filter(department=department, joined_on__lte=cutoff, user__is_active=True)
        .exclude(id__in=[i for i in exclude_ids if i])
        .annotate(current=Count("buddy_for", filter=Q(buddy_for__status=EmployeeStatus.ONBOARDING)))
        .order_by("current", "-joined_on", "code")
        .first()
    )


def template_for(department) -> list:
    return list(
        OnboardingTemplateItem.objects.filter(active=True)
        .filter(Q(department_name="") | Q(department_name=department.name))
        .order_by("order", "title")
    )


def _owner(kind, employee) -> object | None:
    if kind == TaskOwner.EMPLOYEE:
        return employee.user
    if kind == TaskOwner.MANAGER:
        return employee.manager.user if employee.manager else None
    if kind == TaskOwner.BUDDY:
        return employee.buddy.user if employee.buddy else None
    return None  # HR and IT tasks: any HR


def generate_checklist(employee) -> int:
    rows = []
    for item in template_for(employee.department):
        rows.append(
            OnboardingTask(
                employee=employee,
                order=item.order,
                title=item.title,
                description=item.description,
                category=item.category,
                owner_kind=item.owner,
                owner=_owner(item.owner, employee),
                kind=item.kind,
                due_on=add_working_days(employee.location, employee.joined_on, item.due_offset_days),
            )
        )
    OnboardingTask.objects.bulk_create(rows)
    return len(rows)


def generate_first_week(employee) -> int:
    manager = employee.manager.user if employee.manager else None
    buddy = employee.buddy.user if employee.buddy else None
    plan = [
        (0, time(10, 0), "Welcome, ID card and laptop handover", None, "HR and IT desk"),
        (0, time(15, 0), "Meet your manager: goals for the first 30 days", manager, ""),
        (1, time(11, 0), f"{employee.department.name}: how the team works", manager, ""),
        (1, time(13, 0), "Lunch with your buddy", buddy, "" if buddy else "Your buddy"),
        (2, time(11, 0), "Product walkthrough", None, "Product team"),
        (3, time(16, 0), "Policies, leave and attendance in TalentPath", None, "HR"),
        (4, time(16, 30), "Week-one check-in", manager, ""),
    ]
    rows = [
        FirstWeekSession(
            employee=employee,
            day=add_working_days(employee.location, employee.joined_on, offset),
            starts=starts,
            title=title,
            host=host,
            host_label=label or (host.full_name if host else ""),
        )
        for offset, starts, title, host, label in plan
    ]
    FirstWeekSession.objects.bulk_create(rows)
    return len(rows)


def _withdraw_others(application, actor) -> int:
    from applications.services import WITHDRAWABLE, _coordinate, broadcast_board
    from offers.models import LIVE_STATUSES, Offer, OfferStatus

    count = 0
    others = application.candidate.applications.exclude(pk=application.pk).filter(status__in=WITHDRAWABLE)
    for other in others.select_related("job", "job__created_by"):
        old = other.status
        other.status = S.WITHDRAWN
        other.save(update_fields=["status", "updated_at"])
        ApplicationEvent.objects.create(
            application=other, from_status=old, to_status=S.WITHDRAWN, actor=actor, reason="hired_elsewhere"
        )
        Offer.objects.filter(application=other, status__in=LIVE_STATUSES).exclude(
            status=OfferStatus.ACCEPTED
        ).update(status=OfferStatus.REVOKED, revoked_at=timezone.now())
        broadcast_board(other)
        _coordinate(other, old, S.WITHDRAWN, actor, True)
        notify(
            other.job.created_by,
            kind="application_status",
            title=f"Application closed: {other.job.title}",
            body=f"{application.candidate.full_name} joined Lumina Works through another role, "
            "so this application was withdrawn.",
            link=f"/recruiter/jobs/{other.job_id}/board",
            email=False,
        )
        count += 1
    return count


def hire(offer, actor, request=None, now=None) -> Employee:
    from offers.models import Offer, OfferStatus

    now = now or timezone.now()
    today = today_ist(now)
    with transaction.atomic():
        offer = (
            Offer.objects.select_for_update()
            .select_related("application", "application__job", "application__candidate")
            .get(pk=offer.pk)
        )
        application = offer.application
        candidate = application.candidate
        job = application.job
        if offer.status != OfferStatus.ACCEPTED:
            raise ValidationError({"status": "Only an accepted offer can be hired."})
        if application.status != S.OFFER:
            raise ValidationError(
                {"status": "This candidate has already been hired or is no longer at Offer."}
            )
        existing = (
            Employee.objects.select_related("department", "manager__user").filter(user=candidate).first()
        )
        terms = offer.data
        try:
            joining = date.fromisoformat(terms.get("joining_date", ""))
        except ValueError as exc:
            raise ValidationError({"joining_date": "The offer has no joining date."}) from exc
        department = Department.objects.filter(name=terms.get("department")).first() or job.department
        location = Location.objects.filter(name=terms.get("location")).first() or job.location
        manager_user = User.objects.filter(
            pk=terms.get("reporting_manager_id") or None, is_active=True
        ).first()
        if manager_user is None:
            raise ValidationError({"reporting_manager": "The offer's reporting manager is no longer active."})
        manager = ensure_employee(
            manager_user,
            department=department,
            location=location,
            designation=manager_user.get_role_display(),
        )
        if existing is not None:
            return _internal_move(
                existing,
                offer,
                application,
                job,
                actor,
                department=department,
                location=location,
                manager=manager,
                designation=terms.get("designation") or job.title,
                joining=joining,
                request=request,
                now=now,
            )

        # 1. Application -> Hired.
        application.status = S.HIRED
        application.save(update_fields=["status", "updated_at"])
        ApplicationEvent.objects.create(
            application=application, from_status=S.OFFER, to_status=S.HIRED, actor=actor
        )

        # 2. Employee record.
        employee = Employee.objects.create(
            user=candidate,
            code=next_code(),
            designation=terms.get("designation") or job.title,
            department=department,
            location=location,
            manager=manager,
            joined_on=joining,
            level=job.level,
            status=EmployeeStatus.ONBOARDING,
            hired_from=offer,
            company=job.company,
        )
        employee.buddy = choose_buddy(department, joining, exclude_ids=(employee.id, manager.id))
        employee.save(update_fields=["buddy"])

        # 3. Same login, new role (through the policy layer: this view's action is onboarding.hire).
        old_role = candidate.role
        candidate.role = Role.EMPLOYEE
        candidate.save(update_fields=["role"])
        revoke_sessions(candidate)
        audit(
            request,
            "users.role_changed",
            actor=actor,
            target=candidate,
            old=old_role,
            new=Role.EMPLOYEE,
            reason="hired",
        )

        # 4. Leave balances, prorated by the joining date (credited from the joining date on).
        credited = leave_engine.credit_entitlements(employee, max(today, joining))

        # 5. Checklist and first-week plan.
        tasks = generate_checklist(employee)
        sessions = generate_first_week(employee)

        # 6. Other applications and the job.
        withdrawn = _withdraw_others(application, actor)
        job.openings = max(0, job.openings - 1)
        fields = ["openings", "updated_at"]
        if job.openings == 0 and job.status == JobStatus.OPEN:
            job.status, job.closed_at = JobStatus.CLOSED, now
            fields += ["status", "closed_at"]
        job.save(update_fields=fields)

        from applications.services import _coordinate, broadcast_board

        _coordinate(application, S.OFFER, S.HIRED, actor, True)
        audit(
            request,
            "onboarding.hired",
            actor=actor,
            target=employee,
            offer=str(offer.id),
            tasks=tasks,
            sessions=sessions,
            leave_entries=credited,
            withdrawn=withdrawn,
            job_closed=job.status == JobStatus.CLOSED,
        )
        transaction.on_commit(lambda: broadcast_board(application))
        transaction.on_commit(lambda: _welcome_messages(employee.pk))
    return employee


def _internal_move(
    employee,
    offer,
    application,
    job,
    actor,
    *,
    department,
    location,
    manager,
    designation,
    joining,
    request,
    now,
) -> Employee:
    """Internal hire (week 4A): the same employee record changes department, designation, manager
    and level. No new account, no role change; leave balances stay. Audited and recorded."""
    from .models import InternalMove

    if manager.id == employee.id:  # nobody reports to themselves
        manager = employee.manager
    before = {
        "department": employee.department.name,
        "designation": employee.designation,
        "manager": employee.manager.name if employee.manager else "",
    }
    application.status = S.HIRED
    application.save(update_fields=["status", "updated_at"])
    ApplicationEvent.objects.create(
        application=application, from_status=S.OFFER, to_status=S.HIRED, actor=actor
    )
    employee.department, employee.location, employee.designation = department, location, designation
    employee.manager, employee.level, employee.hired_from = manager, job.level, offer
    employee.save(update_fields=["department", "location", "designation", "manager", "level", "hired_from"])
    move = InternalMove.objects.create(
        employee=employee,
        application=application,
        from_department=before["department"],
        to_department=department.name,
        from_designation=before["designation"],
        to_designation=designation,
        from_manager=before["manager"],
        to_manager=manager.name if manager else "",
        moved_on=joining,
    )
    withdrawn = _withdraw_others(application, actor)
    job.openings = max(0, job.openings - 1)
    fields = ["openings", "updated_at"]
    if job.openings == 0 and job.status == JobStatus.OPEN:
        job.status, job.closed_at = JobStatus.CLOSED, now
        fields += ["status", "closed_at"]
    job.save(update_fields=fields)
    from applications.services import _coordinate, broadcast_board

    _coordinate(application, S.OFFER, S.HIRED, actor, True)
    audit(
        request,
        "onboarding.internal_move",
        actor=actor,
        target=employee,
        offer=str(offer.id),
        move=str(move.id),
        from_department=before["department"],
        to_department=department.name,
        withdrawn=withdrawn,
    )
    transaction.on_commit(lambda: broadcast_board(application))
    transaction.on_commit(lambda: _move_messages(employee.pk))
    return employee


def _move_messages(employee_id) -> None:
    employee = Employee.objects.select_related("user", "manager__user", "department").get(pk=employee_id)
    notify(
        employee.user,
        kind="internal_move",
        title=f"Congratulations on your new role: {employee.designation}",
        body=f"You move to {employee.department.name}"
        + (f", reporting to {employee.manager.name}." if employee.manager else "."),
        link="/career",
    )
    if employee.manager:
        notify(
            employee.manager.user,
            kind="new_joiner",
            title=f"{employee.name} joins your team through an internal move",
            body=f"{employee.name} moves into the role of {employee.designation}.",
            link="/team-calendar",
            email=False,
        )


def _welcome_messages(employee_id) -> None:
    employee = Employee.objects.select_related("user", "manager__user", "buddy__user", "department").get(
        pk=employee_id
    )
    start = employee.joined_on.strftime("%a %d %b %Y").replace(" 0", " ")
    notify(
        employee.user,
        kind="welcome",
        title=f"Welcome to Lumina Works, {employee.user.full_name.split()[0]}",
        body=f"Your employee ID is {employee.code} and your first day is {start}. "
        "Sign in to see your checklist, your buddy and your first-week plan.",
        link="/welcome",
    )
    if employee.manager:
        notify(
            employee.manager.user,
            kind="new_joiner",
            title=f"{employee.name} joins your team on {start}",
            body="You have onboarding tasks on their checklist.",
            link=f"/onboarding/{employee.id}",
        )
    if employee.buddy:
        notify(
            employee.buddy.user,
            kind="buddy_assigned",
            title=f"You are {employee.name}'s onboarding buddy",
            body=f"They join {employee.department.name} on {start}. Lunch on day two is on the plan.",
            link=f"/onboarding/{employee.id}",
        )
    for admin in User.objects.filter(role=Role.HR, is_active=True):
        notify(
            admin,
            kind="new_joiner",
            title=f"New joiner: {employee.name} ({employee.code})",
            body="HR and IT tasks are waiting on the onboarding checklist.",
            link=f"/onboarding/{employee.id}",
            email=False,
        )


# ---------------------------------------------------------------- checklist actions
def progress(employee) -> dict:
    tasks = list(employee.tasks.all())
    done = sum(1 for t in tasks if t.done_at)
    return {"done": done, "total": len(tasks), "percent": round(100 * done / len(tasks)) if tasks else 100}


def can_complete(task, user) -> bool:
    if task.owner_id is not None:
        return task.owner_id == user.id or user.role == Role.HR
    return user.role == Role.HR


def complete(task, user, *, document=None, request=None) -> OnboardingTask:
    from .models import TaskKind

    if task.done_at:
        raise ValidationError({"task": "Already done."})
    if task.kind == TaskKind.UPLOAD and document is None and task.document_id is None:
        raise ValidationError({"document": "Upload the document first (PDF, PNG or JPEG, up to 5 MB)."})
    with transaction.atomic():
        if document is not None:
            from files.storage import save_file

            task.document = save_file(
                owner=user, original_name=document[0], content_type=document[1], raw=document[2]
            )
        task.done_at, task.done_by = timezone.now(), user
        task.save()
        employee = task.employee
        if (
            employee.status == EmployeeStatus.ONBOARDING
            and not employee.tasks.filter(done_at__isnull=True).exists()
        ):
            employee.status = EmployeeStatus.ACTIVE
            employee.save(update_fields=["status"])
    audit(request, "onboarding.task_done", actor=user, target=task, employee=str(task.employee_id))
    return task


def reopen(task, user, request=None) -> OnboardingTask:
    task.done_at = task.done_by = None
    task.save(update_fields=["done_at", "done_by"])
    audit(request, "onboarding.task_reopened", actor=user, target=task)
    return task

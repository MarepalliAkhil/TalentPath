from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from accounts.models import Role
from core.audit import audit
from core.views import PolicyAPIView
from files.storage import read_file
from interviews.timeutil import fmt, today_ist
from org.models import Location

from . import attendance, onboarding, team
from . import leave as engine
from .calendar_rules import policy_for
from .models import (
    AttendanceRecord,
    Employee,
    EmployeeStatus,
    HandbookSection,
    Holiday,
    LeaveCode,
    LeaveRequest,
    LeaveType,
    OnboardingTask,
    Regularisation,
    WorkPolicy,
)

MAX_DOC_BYTES = 5 * 1024 * 1024
DOC_TYPES = {b"%PDF-": "application/pdf", b"\x89PNG\r\n\x1a\n": "image/png", b"\xff\xd8\xff": "image/jpeg"}


# ---------------------------------------------------------------- helpers
def read_document(request, field="document"):
    upload = request.FILES.get(field)
    if upload is None:
        return None
    if upload.size > MAX_DOC_BYTES:
        raise ValidationError({field: "Keep documents under 5 MB."})
    raw = upload.read(MAX_DOC_BYTES + 1)
    content_type = next((ct for magic, ct in DOC_TYPES.items() if raw.startswith(magic)), None)
    if content_type is None:
        raise ValidationError({field: "Upload a PDF, PNG or JPEG file."})
    name = (upload.name or "document").rsplit("/", 1)[-1][:120]
    return name, content_type, raw


def me(request) -> Employee:
    employee = (
        Employee.objects.select_related("user", "department", "location", "manager__user", "buddy__user")
        .filter(user=request.user)
        .first()
    )
    if employee is None:
        raise NotFound("You do not have an employee record yet.")
    return employee


def maybe_me(request):
    return Employee.objects.select_related("location", "manager").filter(user=request.user).first()


def person(emp) -> dict | None:
    if emp is None:
        return None
    return {
        "id": str(emp.id),
        "name": emp.name,
        "designation": emp.designation,
        "department": emp.department.name,
        "email": emp.user.email,
    }


def task_dict(task, viewer) -> dict:
    return {
        "id": str(task.id),
        "title": task.title,
        "description": task.description,
        "category": task.category,
        "category_label": task.get_category_display(),
        "owner_kind": task.owner_kind,
        "owner_label": task.get_owner_kind_display(),
        "owner_name": task.owner.full_name
        if task.owner
        else ("HR" if task.owner_kind != "it" else "IT desk"),
        "kind": task.kind,
        "due_on": task.due_on.isoformat(),
        "done": task.done_at is not None,
        "done_at": task.done_at.isoformat() if task.done_at else None,
        "done_by": task.done_by.full_name if task.done_by else None,
        "has_document": task.document_id is not None,
        "can_complete": task.done_at is None and onboarding.can_complete(task, viewer),
        "overdue": task.done_at is None and task.due_on < today_ist(timezone.now()),
    }


def onboarding_dict(emp, viewer) -> dict:
    return {
        "employee": {
            "id": str(emp.id),
            "code": emp.code,
            "name": emp.name,
            "designation": emp.designation,
            "department": emp.department.name,
            "location": emp.location.name,
            "joined_on": emp.joined_on.isoformat(),
            "status": emp.status,
        },
        "manager": person(emp.manager),
        "buddy": person(emp.buddy),
        "progress": onboarding.progress(emp),
        "tasks": [task_dict(t, viewer) for t in emp.tasks.select_related("owner", "done_by")],
        "first_week": [
            {
                "day": s.day.isoformat(),
                "starts": s.starts.strftime("%H:%M"),
                "title": s.title,
                "host": s.host_label or (s.host.full_name if s.host else ""),
            }
            for s in emp.sessions.select_related("host")
        ],
        "welcome_pending": emp.welcome_seen_at is None and emp.tasks.exists(),
    }


def onboarding_scope(user):
    qs = (
        Employee.objects.select_related("user", "department", "location", "manager__user", "buddy__user")
        .filter(tasks__isnull=False)
        .distinct()
    )
    if user.role == Role.HR_ADMIN:
        return qs
    return qs.filter(Q(manager__user=user) | Q(buddy__user=user))


# ---------------------------------------------------------------- onboarding
class HireView(PolicyAPIView):
    policy_action = "onboarding.hire"

    def post(self, request, pk):
        from offers.services import visible_offers

        offer = get_object_or_404(visible_offers(request.user), pk=pk)
        if request.user.role == Role.RECRUITER and offer.application.job.created_by_id != request.user.id:
            raise NotFound()
        employee = onboarding.hire(offer, request.user, request=request)
        employee = Employee.objects.select_related(
            "user", "department", "location", "manager__user", "buddy__user"
        ).get(pk=employee.pk)
        return Response(onboarding_dict(employee, request.user), status=201)


class MyOnboardingView(PolicyAPIView):
    policy_actions = {"GET": "onboarding.mine", "POST": "onboarding.mine"}

    def get(self, request):
        emp = me(request)
        return Response(onboarding_dict(emp, request.user))

    def post(self, request):
        emp = me(request)
        if emp.welcome_seen_at is None:
            emp.welcome_seen_at = timezone.now()
            emp.save(update_fields=["welcome_seen_at"])
        return Response({"ok": True})


class OnboardingListView(PolicyAPIView):
    policy_action = "onboarding.list"

    def get(self, request):
        rows = []
        for emp in onboarding_scope(request.user).order_by("-joined_on"):
            if (
                request.query_params.get("all") not in ("1", "true")
                and emp.status != EmployeeStatus.ONBOARDING
            ):
                continue
            tasks = list(emp.tasks.all())
            rows.append(
                {
                    "id": str(emp.id),
                    "code": emp.code,
                    "name": emp.name,
                    "designation": emp.designation,
                    "department": emp.department.name,
                    "joined_on": emp.joined_on.isoformat(),
                    "status": emp.status,
                    "manager": emp.manager.name if emp.manager else None,
                    "buddy": emp.buddy.name if emp.buddy else None,
                    "progress": onboarding.progress(emp),
                    "overdue": sum(
                        1 for t in tasks if not t.done_at and t.due_on < today_ist(timezone.now())
                    ),
                    "relationship": "hr"
                    if request.user.role == Role.HR_ADMIN
                    else ("manager" if emp.manager and emp.manager.user_id == request.user.id else "buddy"),
                }
            )
        return Response({"results": rows})


class OnboardingDetailView(PolicyAPIView):
    policy_action = "onboarding.list"

    def get(self, request, pk):
        emp = get_object_or_404(onboarding_scope(request.user), pk=pk)
        return Response(onboarding_dict(emp, request.user))


def _task_for(request, pk):
    task = get_object_or_404(
        OnboardingTask.objects.select_related("employee", "employee__user", "owner"), pk=pk
    )
    user = request.user
    visible = (
        task.employee.user_id == user.id
        or user.role == Role.HR_ADMIN
        or onboarding_scope(user).filter(pk=task.employee_id).exists()
        or task.owner_id == user.id
    )
    if not visible:
        raise NotFound()
    return task


class TaskCompleteView(PolicyAPIView):
    policy_action = "onboarding.task"

    def post(self, request, pk):
        task = _task_for(request, pk)
        if not onboarding.can_complete(task, request.user):
            return Response({"detail": "This task belongs to someone else."}, status=403)
        onboarding.complete(task, request.user, document=read_document(request), request=request)
        return Response(task_dict(task, request.user))


class TaskReopenView(PolicyAPIView):
    policy_action = "onboarding.task"

    def post(self, request, pk):
        task = _task_for(request, pk)
        if not onboarding.can_complete(task, request.user) or task.done_at is None:
            return Response({"detail": "You cannot reopen this task."}, status=403)
        onboarding.reopen(task, request.user, request=request)
        return Response(task_dict(task, request.user))


class TaskDocumentView(PolicyAPIView):
    policy_action = "onboarding.task"

    def get(self, request, pk):
        task = _task_for(request, pk)
        if task.document is None:
            raise NotFound()
        audit(request, "onboarding.document_read", target=task)
        response = HttpResponse(read_file(task.document), content_type=task.document.content_type)
        response["Content-Disposition"] = f'attachment; filename="{task.document.original_name}"'
        return response


# ---------------------------------------------------------------- leave
def leave_dict(req, viewer, *, detail=False) -> dict:
    own = req.employee.user_id == viewer.id
    can_act = engine.can_act(req, viewer)
    show_reason = (
        own
        or can_act
        or viewer.role == Role.HR_ADMIN
        or (req.employee.manager_id and req.employee.manager.user_id == viewer.id)
    )
    data = {
        "id": str(req.id),
        "employee": {"id": str(req.employee_id), "name": req.employee.name, "code": req.employee.code},
        "leave_type": req.leave_type.code,
        "leave_type_name": req.leave_type.name,
        "start": req.start.isoformat(),
        "end": req.end.isoformat(),
        "half": req.half,
        "days": float(req.days),
        "days_label": engine.fmt_days(req.days),
        "status": req.status,
        "status_label": req.get_status_display(),
        "stage": req.stage,
        "approver": req.approver.full_name if req.approver else ("HR" if req.status == "pending" else None),
        "delegated": req.delegated,
        "escalated": req.escalated,
        "reason": req.reason if show_reason else None,
        "has_document": req.document_id is not None,
        "decision_note": req.decision_note if (own or can_act or viewer.role == Role.HR_ADMIN) else None,
        "created_at": req.created_at.isoformat(),
        "can_cancel": own and req.status in engine.OPEN and req.start > today_ist(timezone.now()),
        "can_act": can_act,
    }
    if detail or can_act:
        days = [
            r["date"]
            for r in engine.count_days(
                req.employee, req.leave_type, req.start, req.end, req.half, exclude=req
            )[1]
            if r["counted"] > 0
        ]
        data["warnings"] = (
            team.clash_warnings(req.employee, days, exclude=req) if req.status == "pending" else []
        )
    if detail:
        data["timeline"] = [
            {
                "action": a.action,
                "detail": a.detail,
                "actor": a.actor.full_name if a.actor else "TalentPath",
                "at": a.created_at.isoformat(),
            }
            for a in req.actions.select_related("actor")
        ]
    return data


def leave_scope(user):
    qs = LeaveRequest.objects.select_related(
        "employee", "employee__user", "employee__manager", "employee__location", "leave_type", "approver"
    )
    if user.role == Role.HR_ADMIN:
        return qs
    return qs.filter(Q(employee__user=user) | Q(approver=user) | Q(employee__manager__user=user))


class LeaveBalancesView(PolicyAPIView):
    policy_action = "leave.read"

    def get(self, request):
        emp = me(request)
        types = [
            {
                "code": lt.code,
                "name": lt.name,
                "half_day_allowed": lt.half_day_allowed,
                "unpaid": lt.unpaid,
                "min_notice_days": lt.min_notice_days,
                "document_after_days": lt.document_after_days,
            }
            for lt in LeaveType.objects.filter(location=emp.location, active=True).order_by("code")
        ]
        return Response(
            {
                "year": today_ist(timezone.now()).year,
                "balances": engine.balances(emp),
                "types": types,
                "hr_approval_over_days": float(policy_for(emp.location).hr_approval_over_days),
            }
        )


class LeavePreviewView(PolicyAPIView):
    policy_action = "leave.apply"

    def post(self, request):
        emp = me(request)
        has_doc = str(request.data.get("has_document", "")).lower() in ("1", "true")
        return Response(engine.check(emp, request.data, has_document=has_doc).as_dict())


class LeaveRequestsView(PolicyAPIView):
    policy_actions = {"GET": "leave.read", "POST": "leave.apply"}

    def get(self, request):
        emp = me(request)
        qs = leave_scope(request.user).filter(employee=emp)
        if request.query_params.get("status"):
            qs = qs.filter(status=request.query_params["status"])
        return Response({"results": [leave_dict(r, request.user) for r in qs[:100]]})

    def post(self, request):
        emp = me(request)
        leave = engine.apply(
            emp, request.user, request.data, document=read_document(request), request=request
        )
        leave = leave_scope(request.user).get(pk=leave.pk)
        return Response(leave_dict(leave, request.user, detail=True), status=201)


class LeaveDetailView(PolicyAPIView):
    policy_action = "leave.read"

    def get(self, request, pk):
        req = get_object_or_404(leave_scope(request.user), pk=pk)
        return Response(leave_dict(req, request.user, detail=True))


class LeaveDocumentView(PolicyAPIView):
    policy_action = "leave.read"

    def get(self, request, pk):
        req = get_object_or_404(leave_scope(request.user), pk=pk)
        if req.document is None:
            raise NotFound()
        audit(request, "leave.document_read", target=req)
        response = HttpResponse(read_file(req.document), content_type=req.document.content_type)
        response["Content-Disposition"] = f'attachment; filename="{req.document.original_name}"'
        return response


class LeaveCancelView(PolicyAPIView):
    policy_action = "leave.apply"

    def post(self, request, pk):
        req = get_object_or_404(leave_scope(request.user), pk=pk, employee__user=request.user)
        engine.cancel(req, request.user, request=request)
        req.refresh_from_db()
        return Response(leave_dict(req, request.user))


class LeaveDecisionView(PolicyAPIView):
    policy_action = "leave.approve"
    decision = "approve"

    def post(self, request, pk):
        req = get_object_or_404(leave_scope(request.user), pk=pk)
        if req.employee.user_id == request.user.id:
            return Response({"detail": "You cannot approve or reject your own leave."}, status=403)
        note = str(request.data.get("note") or "")
        if self.decision == "approve":
            engine.approve(req, request.user, note, request=request)
        else:
            engine.reject(req, request.user, note, request=request)
        req = leave_scope(request.user).get(pk=pk)
        return Response(leave_dict(req, request.user))


class ApprovalsView(PolicyAPIView):
    policy_action = "leave.approve"

    def get(self, request):
        user = request.user
        data = {
            "leave": [leave_dict(r, user) for r in engine.approvals_for(user)],
            "regularisations": [reg_dict(r, user) for r in attendance.regularisations_for(user)],
            "needs_attention": [],
        }
        if user.role == Role.HR_ADMIN:
            data["needs_attention"] = [leave_dict(r, user) for r in engine.needs_attention()]
        return Response(data)


class LeaveAdjustView(PolicyAPIView):
    policy_action = "leave.adjust"

    def post(self, request):
        emp = (
            get_object_or_404(Employee, pk=request.data.get("employee") or None)
            if _uuid(request.data.get("employee"))
            else None
        )
        if emp is None:
            return Response({"employee": "Choose an employee."}, status=400)
        lt = LeaveType.objects.filter(location=emp.location, code=request.data.get("leave_type")).first()
        if lt is None:
            return Response({"leave_type": "Choose a leave type for the employee's location."}, status=400)
        try:
            days = Decimal(str(request.data.get("days")))
        except (InvalidOperation, ValueError):
            return Response({"days": "Enter a number of days."}, status=400)
        engine.adjust(emp, lt, days, str(request.data.get("note") or ""), request.user, request=request)
        return Response({"balances": engine.balances(emp)}, status=201)


def _uuid(value) -> bool:
    import uuid

    try:
        uuid.UUID(str(value))
    except (ValueError, TypeError):
        return False
    return True


# ---------------------------------------------------------------- team calendar
class TeamCalendarView(PolicyAPIView):
    policy_action = "team.calendar"

    def get(self, request):
        today = today_ist(timezone.now())
        month = attendance.month_bounds(request.query_params.get("month"), today)
        viewer = maybe_me(request)
        team_of = None
        manager_id = request.query_params.get("manager")
        if manager_id:
            if not _uuid(manager_id):
                return Response({"manager": "Unknown team."}, status=400)
            team_of = Employee.objects.filter(pk=manager_id).select_related("user", "location").first()
            allowed = team_of is not None and (
                request.user.role == Role.HR_ADMIN or team_of.user_id == request.user.id
            )
            if not allowed:
                raise NotFound()
        elif viewer is None:
            raise NotFound("You do not have an employee record yet.")
        elif request.query_params.get("view") == "reports" and viewer.reports.exists():
            team_of = viewer
        data = team.calendar(request.user, viewer or team_of, month, team_of=team_of)
        data["has_reports"] = bool(viewer and viewer.reports.exists())
        data["me"] = str(viewer.id) if viewer else None
        return Response(data)


# ---------------------------------------------------------------- holidays, handbook, config
def leave_type_dict(lt) -> dict:
    from .assistant import describe_leave_type

    return {
        "id": str(lt.id),
        "location": str(lt.location_id),
        "location_name": lt.location.name,
        "code": lt.code,
        "name": lt.name,
        "yearly_quota": float(lt.yearly_quota),
        "monthly_accrual": lt.monthly_accrual,
        "prorate_joiners": lt.prorate_joiners,
        "carry_forward_cap": float(lt.carry_forward_cap),
        "min_notice_days": lt.min_notice_days,
        "backdate_days": lt.backdate_days,
        "max_consecutive_days": lt.max_consecutive_days,
        "half_day_allowed": lt.half_day_allowed,
        "document_after_days": lt.document_after_days,
        "sandwich_rule": lt.sandwich_rule,
        "unpaid": lt.unpaid,
        "active": lt.active,
        "summary": describe_leave_type(lt),
    }


def holiday_dict(h) -> dict:
    return {
        "id": str(h.id),
        "date": h.date.isoformat(),
        "name": h.name,
        "regional": h.regional,
        "note": h.note,
    }


def work_policy_dict(p) -> dict:
    return {
        "location": str(p.location_id),
        "location_name": p.location.name,
        "shift_start": p.shift_start.strftime("%H:%M"),
        "shift_end": p.shift_end.strftime("%H:%M"),
        "late_grace_minutes": p.late_grace_minutes,
        "early_grace_minutes": p.early_grace_minutes,
        "weekly_off": p.weekly_off,
        "hr_approval_over_days": float(p.hr_approval_over_days),
        "min_team_available_pct": p.min_team_available_pct,
        "escalate_after_hours": p.escalate_after_hours,
    }


class PoliciesView(PolicyAPIView):
    """Handbook and the signed-in person's location rules, holidays included."""

    policy_action = "hr.read"

    def get(self, request):
        emp = maybe_me(request)
        location = emp.location if emp else None
        loc_param = request.query_params.get("location")
        if loc_param and _uuid(loc_param):
            location = Location.objects.filter(pk=loc_param).first() or location
        year = today_ist(timezone.now()).year
        data = {
            "handbook": [
                {"slug": s.slug, "title": s.title, "body": s.body} for s in HandbookSection.objects.all()
            ],
            "location": {"id": str(location.id), "name": location.name} if location else None,
            "leave_types": [],
            "holidays": [],
            "work_policy": None,
        }
        if location is not None:
            data["leave_types"] = [
                leave_type_dict(lt)
                for lt in LeaveType.objects.filter(location=location, active=True).select_related("location")
            ]
            data["holidays"] = [
                holiday_dict(h)
                for h in Holiday.objects.filter(location=location, date__year__in=[year, year + 1])
            ]
            data["work_policy"] = work_policy_dict(policy_for(location))
        return Response(data)


LEAVE_FIELDS = {
    "name": str,
    "yearly_quota": "dec",
    "monthly_accrual": bool,
    "prorate_joiners": bool,
    "carry_forward_cap": "dec",
    "min_notice_days": "int",
    "backdate_days": "int",
    "max_consecutive_days": "int?",
    "half_day_allowed": bool,
    "document_after_days": "int?",
    "sandwich_rule": bool,
    "unpaid": bool,
    "active": bool,
}


def _apply_fields(obj, data, spec) -> list:
    errors, changed = {}, []
    for key, kind in spec.items():
        if key not in data:
            continue
        value = data[key]
        try:
            if kind is bool:
                if not isinstance(value, bool):
                    raise ValueError
            elif kind is str:
                value = str(value).strip()[:60]
                if not value:
                    raise ValueError
            elif kind == "dec":
                value = engine.round_half(Decimal(str(value)))
                if value < 0 or value > 365:
                    raise ValueError
            elif kind in ("int", "int?"):
                if value in (None, "") and kind == "int?":
                    value = None
                else:
                    value = int(value)
                    if value < 0 or value > 365:
                        raise ValueError
        except (ValueError, TypeError, InvalidOperation):
            errors[key] = "Enter a valid value."
            continue
        setattr(obj, key, value)
        changed.append(key)
    if errors:
        raise ValidationError(errors)
    return changed


class ConfigView(PolicyAPIView):
    policy_action = "hr.config"

    def get(self, request):
        return Response(
            {
                "locations": [{"id": str(loc.id), "name": loc.name} for loc in Location.objects.all()],
                "leave_types": [leave_type_dict(lt) for lt in LeaveType.objects.select_related("location")],
                "work_policies": [work_policy_dict(policy_for(loc)) for loc in Location.objects.all()],
                "holidays": [
                    {**holiday_dict(h), "location": str(h.location_id)}
                    for h in Holiday.objects.filter(date__year__gte=today_ist(timezone.now()).year)
                ],
                "codes": [{"code": c.value, "label": c.label} for c in LeaveCode],
            }
        )


class ConfigLeaveTypesView(PolicyAPIView):
    policy_action = "hr.config"

    def post(self, request):
        location = (
            Location.objects.filter(pk=request.data.get("location")).first()
            if _uuid(request.data.get("location"))
            else None
        )
        code = request.data.get("code")
        if location is None:
            return Response({"location": "Choose a location."}, status=400)
        if code not in LeaveCode.values:
            return Response({"code": "Choose a leave code."}, status=400)
        if LeaveType.objects.filter(location=location, code=code).exists():
            return Response({"code": "This location already has that leave type."}, status=400)
        lt = LeaveType(location=location, code=code, name=LeaveCode(code).label)
        _apply_fields(lt, request.data, LEAVE_FIELDS)
        lt.save()
        audit(request, "hr.leave_type_created", target=lt, code=code)
        return Response(leave_type_dict(lt), status=201)


class ConfigLeaveTypeView(PolicyAPIView):
    policy_action = "hr.config"

    def patch(self, request, pk):
        lt = get_object_or_404(LeaveType.objects.select_related("location"), pk=pk)
        changed = _apply_fields(lt, request.data, LEAVE_FIELDS)
        if changed:
            lt.save()
            audit(request, "hr.leave_type_updated", target=lt, fields=changed)
        return Response(leave_type_dict(lt))


class ConfigHolidaysView(PolicyAPIView):
    policy_action = "hr.config"

    def post(self, request):
        location = (
            Location.objects.filter(pk=request.data.get("location")).first()
            if _uuid(request.data.get("location"))
            else None
        )
        if location is None:
            return Response({"location": "Choose a location."}, status=400)
        try:
            day = date.fromisoformat(str(request.data.get("date")))
        except ValueError:
            return Response({"date": "Choose a date."}, status=400)
        name = str(request.data.get("name") or "").strip()[:120]
        if len(name) < 2:
            return Response({"name": "Name the holiday."}, status=400)
        if Holiday.objects.filter(location=location, date=day).exists():
            return Response({"date": "There is already a holiday on that date."}, status=400)
        h = Holiday.objects.create(
            location=location,
            date=day,
            name=name,
            regional=bool(request.data.get("regional")),
            note=str(request.data.get("note") or "")[:160],
        )
        audit(request, "hr.holiday_created", target=h)
        return Response(holiday_dict(h), status=201)


class ConfigHolidayView(PolicyAPIView):
    policy_action = "hr.config"

    def delete(self, request, pk):
        h = get_object_or_404(Holiday, pk=pk)
        audit(request, "hr.holiday_deleted", target=h, date=h.date.isoformat())
        h.delete()
        return Response(status=204)


class ConfigWorkPolicyView(PolicyAPIView):
    policy_action = "hr.config"

    def patch(self, request, pk):
        location = get_object_or_404(Location, pk=pk)
        p = policy_for(location)
        errors = {}
        for key in ("shift_start", "shift_end"):
            if key in request.data:
                try:
                    hours, minutes = str(request.data[key]).split(":")[:2]
                    setattr(
                        p,
                        key,
                        timezone.datetime.strptime(f"{int(hours):02d}:{int(minutes):02d}", "%H:%M").time(),
                    )
                except (ValueError, TypeError):
                    errors[key] = "Use a time like 09:30."
        for key, low, high in (
            ("late_grace_minutes", 0, 240),
            ("early_grace_minutes", 0, 240),
            ("min_team_available_pct", 0, 100),
            ("escalate_after_hours", 1, 720),
        ):
            if key in request.data:
                try:
                    value = int(request.data[key])
                    if not low <= value <= high:
                        raise ValueError
                    setattr(p, key, value)
                except (ValueError, TypeError):
                    errors[key] = f"Enter a whole number from {low} to {high}."
        if "hr_approval_over_days" in request.data:
            try:
                p.hr_approval_over_days = engine.round_half(
                    Decimal(str(request.data["hr_approval_over_days"]))
                )
            except (InvalidOperation, ValueError):
                errors["hr_approval_over_days"] = "Enter a number of days."
        if "weekly_off" in request.data:
            value = request.data["weekly_off"]
            if (
                not isinstance(value, list)
                or not all(isinstance(v, int) and 1 <= v <= 7 for v in value)
                or len(value) > 3
            ):
                errors["weekly_off"] = "Choose up to three weekdays (1 = Monday ... 7 = Sunday)."
            else:
                p.weekly_off = sorted(set(value))
        if errors:
            return Response(errors, status=400)
        if p.shift_end <= p.shift_start:
            return Response({"shift_end": "The shift must end after it starts."}, status=400)
        p.save()
        audit(request, "hr.work_policy_updated", target=p)
        return Response(work_policy_dict(p))


class AttentionView(PolicyAPIView):
    policy_action = "hr.attention"

    def get(self, request):
        today = today_ist(timezone.now())
        overdue = (
            OnboardingTask.objects.filter(done_at__isnull=True, due_on__lt=today)
            .select_related("employee", "employee__user")
            .order_by("due_on")[:50]
        )
        no_buddy = Employee.objects.filter(
            status=EmployeeStatus.ONBOARDING, buddy__isnull=True
        ).select_related("user")
        return Response(
            {
                "leave": [leave_dict(r, request.user) for r in engine.needs_attention()],
                "overdue_tasks": [
                    {
                        "employee": str(t.employee_id),
                        "name": t.employee.name,
                        "title": t.title,
                        "due_on": t.due_on.isoformat(),
                    }
                    for t in overdue
                ],
                "no_buddy": [{"employee": str(e.id), "name": e.name} for e in no_buddy],
            }
        )


# ---------------------------------------------------------------- attendance
def reg_dict(reg, viewer) -> dict:
    own = reg.employee.user_id == viewer.id
    return {
        "id": str(reg.id),
        "employee": {"id": str(reg.employee_id), "name": reg.employee.name},
        "date": reg.date.isoformat(),
        "check_in": reg.check_in.strftime("%H:%M"),
        "check_out": reg.check_out.strftime("%H:%M"),
        "mode": reg.mode,
        "reason": reg.reason
        if (own or attendance.can_decide(reg, viewer) or viewer.role == Role.HR_ADMIN)
        else None,
        "status": reg.status,
        "status_label": reg.get_status_display(),
        "approver": reg.approver.full_name if reg.approver else "HR",
        "decision_note": reg.decision_note,
        "can_decide": attendance.can_decide(reg, viewer),
    }


def record_dict(rec) -> dict | None:
    if rec is None:
        return None
    return {
        "date": rec.date.isoformat(),
        "check_in": fmt(rec.check_in) if rec.check_in else None,
        "check_out": fmt(rec.check_out) if rec.check_out else None,
        "mode": rec.mode,
        "late": rec.late,
        "early": rec.early,
    }


class AttendanceMeView(PolicyAPIView):
    policy_action = "attendance.read"

    def get(self, request):
        emp = me(request)
        today = today_ist(timezone.now())
        month = attendance.month_bounds(request.query_params.get("month"), today)
        policy = policy_for(emp.location)
        return Response(
            {
                "today": record_dict(attendance.today_record(emp)),
                "shift": {
                    "start": policy.shift_start.strftime("%H:%M"),
                    "end": policy.shift_end.strftime("%H:%M"),
                    "late_grace_minutes": policy.late_grace_minutes,
                    "early_grace_minutes": policy.early_grace_minutes,
                    "location": emp.location.name,
                },
                "summary": attendance.summary(emp, month, today=today),
                "regularisations": [
                    reg_dict(r, request.user)
                    for r in Regularisation.objects.filter(employee=emp).select_related(
                        "employee", "employee__user", "approver"
                    )[:20]
                ],
            }
        )


class CheckInView(PolicyAPIView):
    policy_action = "attendance.check"
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "hira"

    def post(self, request):
        emp = me(request)
        rec = attendance.check_in(emp, str(request.data.get("mode") or "office"), request=request)
        return Response(record_dict(rec), status=201)


class CheckOutView(PolicyAPIView):
    policy_action = "attendance.check"

    def post(self, request):
        emp = me(request)
        rec = attendance.check_out(emp, request=request)
        return Response(record_dict(rec))


class RegularisationsView(PolicyAPIView):
    policy_action = "attendance.regularise"

    def post(self, request):
        emp = me(request)
        reg = attendance.request_regularisation(emp, request.data, request=request)
        reg = Regularisation.objects.select_related("employee", "employee__user", "approver").get(pk=reg.pk)
        return Response(reg_dict(reg, request.user), status=201)


class RegularisationDecideView(PolicyAPIView):
    policy_action = "attendance.approve"

    def post(self, request, pk):
        reg = get_object_or_404(
            Regularisation.objects.select_related("employee", "employee__user", "approver"), pk=pk
        )
        user = request.user
        if not (reg.approver_id == user.id or user.role == Role.HR_ADMIN or reg.employee.user_id == user.id):
            raise NotFound()
        if reg.employee.user_id == user.id:
            return Response({"detail": "You cannot approve your own attendance correction."}, status=403)
        approve = str(request.data.get("decision")) == "approve"
        reg = attendance.decide(reg, user, approve, str(request.data.get("note") or ""), request=request)
        return Response(reg_dict(reg, user))


class AttendanceTeamView(PolicyAPIView):
    policy_action = "attendance.team"

    def get(self, request):
        today = today_ist(timezone.now())
        month = attendance.month_bounds(request.query_params.get("month"), today)
        viewer = maybe_me(request)
        people = attendance.employees_in_scope(request.user, viewer)
        dept = request.query_params.get("department")
        if dept and _uuid(dept):
            people = people.filter(department_id=dept)
        return Response(
            {
                "month": month.strftime("%Y-%m"),
                "scope": "all" if request.user.role == Role.HR_ADMIN else "reports",
                "rows": attendance.team_summary(people.order_by("user__full_name")[:200], month, today=today),
            }
        )


__all__ = ["AttendanceRecord", "WorkPolicy", "timedelta"]

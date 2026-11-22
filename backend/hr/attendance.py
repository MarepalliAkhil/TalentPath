"""Web check-in and check-out (no location tracking), shift flags, missing
check-outs, regularisation and monthly summaries."""

from datetime import date, datetime, time, timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from core.audit import audit
from interviews.timeutil import IST, ist, today_ist
from notifications.services import notify

from .calendar_rules import DayBook, date_range, policy_for
from .leave import chain_approver
from .models import (
    AttendanceRecord,
    Employee,
    LeaveRequest,
    LeaveStatus,
    Regularisation,
    RegularisationStatus,
    WorkMode,
)


def _at(day: date, t: time) -> datetime:
    return datetime.combine(day, t, tzinfo=IST)


def flags(employee, day: date, check_in, check_out) -> tuple[bool, bool]:
    """(late, early) against the location's general shift and grace minutes."""
    policy = policy_for(employee.location)
    late = bool(check_in) and ist(check_in) > _at(day, policy.shift_start) + timedelta(
        minutes=policy.late_grace_minutes
    )
    early = bool(check_out) and ist(check_out) < _at(day, policy.shift_end) - timedelta(
        minutes=policy.early_grace_minutes
    )
    return late, early


def today_record(employee, now=None):
    now = now or timezone.now()
    return AttendanceRecord.objects.filter(employee=employee, date=today_ist(now)).first()


def check_in(employee, mode: str, request=None, now=None) -> AttendanceRecord:
    now = now or timezone.now()
    if mode not in WorkMode.values:
        raise ValidationError({"mode": "Choose office or remote."})
    day = today_ist(now)
    with transaction.atomic():
        record, created = AttendanceRecord.objects.select_for_update().get_or_create(
            employee=employee, date=day, defaults={"mode": mode}
        )
        if record.check_in:
            raise ValidationError({"detail": "You have already checked in today."})
        record.check_in, record.mode = now, mode
        record.late, _ = flags(employee, day, now, None)
        record.save()
    audit(request, "attendance.check_in", target=record, mode=mode)
    return record


def check_out(employee, request=None, now=None) -> AttendanceRecord:
    now = now or timezone.now()
    day = today_ist(now)
    with transaction.atomic():
        record = AttendanceRecord.objects.select_for_update().filter(employee=employee, date=day).first()
        if record is None or not record.check_in:
            raise ValidationError({"detail": "Check in first."})
        if record.check_out:
            raise ValidationError({"detail": "You have already checked out today."})
        record.check_out = now
        record.late, record.early = flags(employee, day, record.check_in, now)
        record.missing_checkout = False
        record.save()
    audit(request, "attendance.check_out", target=record)
    return record


def mark_missing_checkouts(now=None) -> int:
    """Earlier days with a check-in and no check-out. Each record is flagged and the person told once."""
    now = now or timezone.now()
    today = today_ist(now)
    count = 0
    for record in AttendanceRecord.objects.filter(
        date__lt=today, check_in__isnull=False, check_out__isnull=True, missing_checkout=False
    ).select_related("employee__user"):
        record.missing_checkout = True
        record.save(update_fields=["missing_checkout", "updated_at"])
        notify(
            record.employee.user,
            kind="attendance_missing",
            title=f"No check-out on {record.date.strftime('%a %d %b').replace(' 0', ' ')}",
            body="Request a regularisation with your actual times so your manager can approve it.",
            link="/attendance",
            email=False,
        )
        count += 1
    return count


# ---------------------------------------------------------------- regularisation
def request_regularisation(employee, data: dict, request=None, now=None) -> Regularisation:
    now = now or timezone.now()
    today = today_ist(now)
    errors = {}
    try:
        day = date.fromisoformat(str(data.get("date") or ""))
    except ValueError:
        day = None
        errors["date"] = "Choose the date to correct."
    times = {}
    for key in ("check_in", "check_out"):
        try:
            hours, minutes = str(data.get(key) or "").split(":")[:2]
            times[key] = time(int(hours), int(minutes))
        except (ValueError, TypeError):
            errors[key] = "Use a time like 09:30."
    mode = str(data.get("mode") or WorkMode.OFFICE)
    if mode not in WorkMode.values:
        errors["mode"] = "Choose office or remote."
    reason = str(data.get("reason") or "").strip()
    if len(reason) < 5:
        errors["reason"] = "Say what happened (at least 5 characters)."
    if day is not None:
        if day >= today:
            errors["date"] = "Regularise a past day; use check-in and check-out for today."
        elif day < today - timedelta(days=30):
            errors["date"] = "Regularisation is open for the last 30 days."
        elif day < employee.joined_on:
            errors["date"] = "That is before your joining date."
        elif not DayBook(employee.location, day, day).is_working(day):
            errors["date"] = "That is a weekly off or a holiday."
        elif Regularisation.objects.filter(
            employee=employee, date=day, status=RegularisationStatus.PENDING
        ).exists():
            errors["date"] = "You already have a pending request for that day."
    if not errors and times["check_out"] <= times["check_in"]:
        errors["check_out"] = "Check-out must be after check-in."
    if errors:
        raise ValidationError(errors)
    approver, _ = chain_approver(employee, today)
    reg = Regularisation.objects.create(
        employee=employee,
        date=day,
        check_in=times["check_in"],
        check_out=times["check_out"],
        mode=mode,
        reason=reason[:500],
        approver=approver,
    )
    if approver:
        notify(
            approver,
            kind="regularisation",
            title=f"Attendance correction to approve: {employee.name}",
            body=f"{day:%d %b}: {times['check_in']:%H:%M} to {times['check_out']:%H:%M}.",
            link="/leave/approvals",
            email=False,
        )
    audit(request, "attendance.regularisation_requested", target=reg)
    return reg


def can_decide(reg, user) -> bool:
    from accounts.models import Role

    if reg.status != RegularisationStatus.PENDING or reg.employee.user_id == user.id:
        return False
    return reg.approver_id == user.id or (reg.approver_id is None and user.role == Role.HR_ADMIN)


def regularisations_for(user):
    from django.db.models import Q

    from accounts.models import Role

    q = Q(approver=user)
    if user.role == Role.HR_ADMIN:
        q |= Q(approver__isnull=True)
    return (
        Regularisation.objects.filter(status=RegularisationStatus.PENDING)
        .filter(q)
        .exclude(employee__user=user)
        .select_related("employee", "employee__user")
    )


def decide(reg, user, approve: bool, note: str = "", request=None) -> Regularisation:
    with transaction.atomic():
        reg = (
            Regularisation.objects.select_for_update()
            .select_related("employee", "employee__user")
            .get(pk=reg.pk)
        )
        if not can_decide(reg, user):
            raise PermissionDenied("This correction is not waiting for you.")
        if not approve and len((note or "").strip()) < 5:
            raise ValidationError({"note": "Say why (at least 5 characters)."})
        reg.status = RegularisationStatus.APPROVED if approve else RegularisationStatus.REJECTED
        reg.decided_by, reg.decided_at, reg.decision_note = user, timezone.now(), (note or "").strip()[:500]
        reg.save()
        if approve:
            record, _ = AttendanceRecord.objects.get_or_create(employee=reg.employee, date=reg.date)
            record.check_in, record.check_out = _at(reg.date, reg.check_in), _at(reg.date, reg.check_out)
            record.mode = reg.mode
            record.late, record.early = flags(reg.employee, reg.date, record.check_in, record.check_out)
            record.missing_checkout, record.regularised = False, True
            record.save()
    notify(
        reg.employee.user,
        kind="regularisation",
        title=f"Attendance correction {'approved' if approve else 'not approved'}: {reg.date:%d %b}",
        body=reg.decision_note or "",
        link="/attendance",
        email=False,
    )
    audit(request, "attendance.regularisation_decided", actor=user, target=reg, approved=approve)
    return reg


# ---------------------------------------------------------------- summaries
def month_bounds(value: str | None, today: date) -> date:
    if value:
        try:
            year, month = (int(p) for p in value.split("-")[:2])
            return date(year, month, 1)
        except (ValueError, TypeError):
            raise ValidationError({"month": "Use a month like 2026-11."}) from None
    return today.replace(day=1)


def summary(employee, month_start: date, *, today: date | None = None) -> dict:
    today = today or today_ist(timezone.now())
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    end = min(next_month - timedelta(days=1), today)
    book = DayBook(employee.location, month_start, next_month)
    records = {
        r.date: r
        for r in AttendanceRecord.objects.filter(
            employee=employee, date__gte=month_start, date__lt=next_month
        )
    }
    leave_days = set()
    for req in LeaveRequest.objects.filter(
        employee=employee, status=LeaveStatus.APPROVED, start__lt=next_month, end__gte=month_start
    ):
        leave_days.update(date_range(req.start, req.end))
    counts = {
        "working_days": 0,
        "present": 0,
        "office": 0,
        "remote": 0,
        "late": 0,
        "early": 0,
        "missing_checkout": 0,
        "on_leave": 0,
        "holidays": 0,
        "absent": 0,
    }
    days = []
    start = max(month_start, employee.joined_on)
    for day in date_range(start, end) if start <= end else []:
        kind = book.kind(day)
        rec = records.get(day)
        status = kind
        if kind == "holiday":
            counts["holidays"] += 1
        if kind == "working":
            counts["working_days"] += 1
            if rec and rec.check_in:
                status = "present"
            elif day in leave_days:
                status = "leave"
            elif day < today:
                status = "absent"
            else:
                status = "today"
        if rec and rec.check_in:
            counts["present"] += 1
            counts[rec.mode] += 1
            counts["late"] += int(rec.late)
            counts["early"] += int(rec.early)
            counts["missing_checkout"] += int(rec.missing_checkout)
        elif status == "leave":
            counts["on_leave"] += 1
        elif status == "absent":
            counts["absent"] += 1
        days.append(
            {
                "date": day.isoformat(),
                "status": status,
                "holiday": book.holiday(day) or "",
                "check_in": ist(rec.check_in).strftime("%H:%M") if rec and rec.check_in else None,
                "check_out": ist(rec.check_out).strftime("%H:%M") if rec and rec.check_out else None,
                "mode": rec.mode if rec and rec.check_in else None,
                "late": bool(rec and rec.late),
                "early": bool(rec and rec.early),
                "missing_checkout": bool(rec and rec.missing_checkout),
                "regularised": bool(rec and rec.regularised),
            }
        )
    return {"month": month_start.strftime("%Y-%m"), "counts": counts, "days": days}


def team_summary(employees, month_start: date, today: date | None = None) -> list[dict]:
    rows = []
    for emp in employees:
        data = summary(emp, month_start, today=today)
        rows.append(
            {
                "employee": str(emp.id),
                "name": emp.name,
                "code": emp.code,
                "department": emp.department.name,
                **data["counts"],
            }
        )
    return rows


def employees_in_scope(user, viewer_employee):
    """hr_admin: everyone; a manager: direct reports; others: nobody else."""
    from accounts.models import Role

    qs = Employee.objects.select_related("user", "department", "location").filter(user__is_active=True)
    if user.role == Role.HR_ADMIN:
        return qs
    if viewer_employee is None:
        return qs.none()
    return qs.filter(manager=viewer_employee)

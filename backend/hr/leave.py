"""Leave engine: day counting, every policy rule, balances, routing, approvals,
delegation, escalation, accrual and carry-forward.

Rules come from `LeaveType` / `WorkPolicy` rows per location (HR edits
them); nothing here hard-codes a quota or a notice period.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import Role
from core.audit import audit
from interviews.timeutil import today_ist
from notifications.services import notify

from .calendar_rules import DayBook, date_range, policy_for
from .models import (
    ApprovalStage,
    Employee,
    HalfDay,
    LeaveAction,
    LeaveLedger,
    LeaveRequest,
    LeaveStatus,
    LeaveType,
    LedgerKind,
)

ZERO = Decimal("0")
HALF = Decimal("0.5")
OPEN = (LeaveStatus.PENDING, LeaveStatus.APPROVED)
MAX_RANGE_DAYS = 60


def round_half(value) -> Decimal:
    """Round to the nearest half day."""
    return (Decimal(value) * 2).quantize(Decimal("1"), rounding=ROUND_HALF_UP) / 2


def fmt_days(value) -> str:
    value = Decimal(value).normalize()
    text = f"{value:f}"
    return f"{text} day" if value == 1 else f"{text} days"


def nice_date(day: date) -> str:
    return day.strftime("%a %d %b %Y").replace(" 0", " ")


# ---------------------------------------------------------------- balances
def ledger_total(employee, leave_type, year: int) -> Decimal:
    total = LeaveLedger.objects.filter(employee=employee, leave_type=leave_type, year=year).aggregate(
        s=Sum("days")
    )["s"]
    return total or ZERO


def pending_days(employee, leave_type, year: int, exclude=None) -> Decimal:
    qs = LeaveRequest.objects.filter(
        employee=employee, leave_type=leave_type, status=LeaveStatus.PENDING, start__year=year
    )
    if exclude is not None:
        qs = qs.exclude(pk=exclude.pk)
    return qs.aggregate(s=Sum("days"))["s"] or ZERO


def taken_days(employee, leave_type, year: int) -> Decimal:
    return (
        LeaveRequest.objects.filter(
            employee=employee, leave_type=leave_type, status=LeaveStatus.APPROVED, start__year=year
        ).aggregate(s=Sum("days"))["s"]
        or ZERO
    )


def _months_from(joined: date, year: int) -> int:
    """First month (1-12) a joiner earns in `year`: the joining month counts if joined by the 15th."""
    if joined.year < year:
        return 1
    if joined.year > year:
        return 13
    return joined.month if joined.day <= 15 else joined.month + 1


def accrual_for_month(quota: Decimal, month: int) -> Decimal:
    """Monthly credit chosen so that twelve months add up to exactly the yearly quota."""
    return round_half(quota * month / 12) - round_half(quota * (month - 1) / 12)


def entitlement_until(leave_type, employee, year: int, month: int) -> Decimal:
    """What the employee earns in `year` up to and including `month` (projection, no carry)."""
    first = _months_from(employee.joined_on, year)
    if first > 12:
        return ZERO
    quota = leave_type.yearly_quota
    if leave_type.monthly_accrual:
        return sum((accrual_for_month(quota, m) for m in range(first, month + 1)), ZERO)
    if first == 1 or not leave_type.prorate_joiners:
        return quota
    return round_half(quota * (13 - first) / 12)


def available(employee, leave_type, year: int, *, today: date, month: int = 12, exclude=None) -> Decimal:
    """Days that can still be requested in `year` (pending requests are already reserved).

    For a future year nothing is credited yet, so the balance is projected: this
    year's unused days up to the carry-forward cap, plus what accrues by `month`.
    """
    if year < today.year:
        return ledger_total(employee, leave_type, year) - pending_days(employee, leave_type, year, exclude)
    if year == today.year:
        # Monthly accruals still to come before the leave's month count too (the nightly job credits them).
        upcoming = ZERO
        if leave_type.monthly_accrual and month > today.month:
            upcoming = entitlement_until(leave_type, employee, year, month) - entitlement_until(
                leave_type, employee, year, today.month
            )
        return (
            ledger_total(employee, leave_type, year)
            + upcoming
            - pending_days(employee, leave_type, year, exclude)
        )
    now_left = max(ZERO, available(employee, leave_type, today.year, today=today, exclude=exclude))
    carry = min(now_left, leave_type.carry_forward_cap)
    return (
        carry
        + entitlement_until(leave_type, employee, year, month)
        - pending_days(employee, leave_type, year, exclude)
    )


def balances(employee, *, today: date | None = None) -> list[dict]:
    today = today or today_ist(timezone.now())
    rows = []
    for lt in LeaveType.objects.filter(location=employee.location, active=True).order_by("code"):
        year = today.year
        if lt.unpaid:
            rows.append(
                {
                    "type": lt.code,
                    "name": lt.name,
                    "unpaid": True,
                    "balance": None,
                    "pending": float(pending_days(employee, lt, year)),
                    "taken": float(taken_days(employee, lt, year)),
                    "available": None,
                    "booked_ahead": 0.0,
                }
            )
            continue
        total = ledger_total(employee, lt, year)
        pend = pending_days(employee, lt, year)
        left = total - pend
        rows.append(
            {
                "type": lt.code,
                "name": lt.name,
                "unpaid": False,
                "balance": float(total),
                "pending": float(pend),
                "taken": float(taken_days(employee, lt, year)),
                "available": float(max(left, ZERO)),
                # Leave booked for a later month against accruals that have not been credited yet.
                "booked_ahead": float(max(-left, ZERO)),
            }
        )
    return rows


def _credit(employee, leave_type, year, kind, days, key, note="") -> bool:
    """Write one ledger row unless its key already exists. Returns True when written."""
    if LeaveLedger.objects.filter(key=key).exists():
        return False
    try:
        with transaction.atomic():
            LeaveLedger.objects.create(
                employee=employee, leave_type=leave_type, year=year, kind=kind, days=days, key=key, note=note
            )
    except IntegrityError:  # a concurrent run wrote it first
        return False
    return True


def credit_entitlements(employee, today: date) -> int:
    """Grant (yearly types) or accrue (monthly types) everything due up to `today`. Idempotent."""
    written = 0
    year = today.year
    first = _months_from(employee.joined_on, year)
    if employee.joined_on > today or first > 12:
        return 0
    for lt in LeaveType.objects.filter(location=employee.location, active=True, unpaid=False):
        if lt.yearly_quota <= 0:
            continue
        if lt.monthly_accrual:
            for month in range(first, today.month + 1):
                amount = accrual_for_month(lt.yearly_quota, month)
                if amount > 0:
                    written += _credit(
                        employee,
                        lt,
                        year,
                        LedgerKind.ACCRUAL,
                        amount,
                        f"accrual:{employee.id}:{lt.id}:{year}-{month:02d}",
                        f"{lt.name} for {date(year, month, 1):%b %Y}",
                    )
        else:
            amount = entitlement_until(lt, employee, year, 12)
            if amount > 0:
                note = f"{lt.name} for {year}" + (" (prorated)" if first > 1 and lt.prorate_joiners else "")
                written += _credit(
                    employee, lt, year, LedgerKind.GRANT, amount, f"grant:{employee.id}:{lt.id}:{year}", note
                )
    return written


def run_accruals(today: date | None = None) -> int:
    today = today or today_ist(timezone.now())
    return sum(
        credit_entitlements(emp, today)
        for emp in Employee.objects.filter(user__is_active=True, joined_on__lte=today).select_related(
            "location"
        )
    )


def run_year_end(today: date | None = None) -> dict:
    """Carry last year's unused days into this year up to the cap; the rest lapses. Idempotent."""
    today = today or today_ist(timezone.now())
    prev = today.year - 1
    carried = lapsed = 0
    for emp in Employee.objects.filter(joined_on__lte=date(prev, 12, 31)):
        for lt in LeaveType.objects.filter(location=emp.location, unpaid=False):
            left = ledger_total(emp, lt, prev)
            if left <= 0:
                continue
            carry = min(left, lt.carry_forward_cap)
            if carry > 0:
                carried += _credit(
                    emp,
                    lt,
                    today.year,
                    LedgerKind.CARRY,
                    carry,
                    f"carry:{emp.id}:{lt.id}:{today.year}",
                    f"Carried forward from {prev}",
                )
            if left - carry > 0:
                lapsed += _credit(
                    emp,
                    lt,
                    prev,
                    LedgerKind.LAPSE,
                    -(left - carry),
                    f"lapse:{emp.id}:{lt.id}:{prev}",
                    f"Above the carry-forward cap of {fmt_days(lt.carry_forward_cap)}",
                )
    return {"carried": carried, "lapsed": lapsed}


def adjust(employee, leave_type, days, note: str, actor, request=None) -> LeaveLedger:
    if leave_type.unpaid:
        raise ValidationError({"leave_type": "Loss of pay has no balance to adjust."})
    days = round_half(days)
    if days == 0:
        raise ValidationError({"days": "Enter a non-zero number of days in half-day steps."})
    if len((note or "").strip()) < 5:
        raise ValidationError({"note": "Say why (at least 5 characters)."})
    year = today_ist(timezone.now()).year
    entry = LeaveLedger.objects.create(
        employee=employee,
        leave_type=leave_type,
        year=year,
        kind=LedgerKind.ADJUST,
        days=days,
        key=f"adjust:{employee.id}:{timezone.now().timestamp()}:{actor.id}",
        note=note.strip()[:200],
    )
    audit(request, "leave.adjusted", actor=actor, target=employee, leave_type=leave_type.code, days=str(days))
    return entry


# ---------------------------------------------------------------- counting
def _covered_by_existing(employee, start: date, end: date, exclude=None) -> set:
    qs = LeaveRequest.objects.filter(
        employee=employee, status__in=OPEN, start__lte=end, end__gte=start, half=""
    )
    if exclude is not None:
        qs = qs.exclude(pk=exclude.pk)
    days = set()
    for req in qs:
        days.update(date_range(req.start, req.end))
    return days


def count_days(employee, leave_type, start: date, end: date, half: str = "", exclude=None):
    """Return (days, breakdown). Breakdown rows: {date, kind, counted, label}.

    With the sandwich rule on, weekly offs and holidays count when leave sits on
    both sides of them, including leave from another request that ends just
    before or starts just after this one.
    """
    book = DayBook(employee.location, start, end)
    if half:
        kind = book.kind(start)
        counted = HALF if kind == "working" else ZERO
        return counted, [
            {"date": start, "kind": kind, "counted": counted, "label": book.holiday(start) or ""}
        ]

    existing = _covered_by_existing(employee, start - timedelta(days=14), end + timedelta(days=14), exclude)

    def leave_day(day):
        return (start <= day <= end and book.is_working(day)) or day in existing

    def sandwiched(day):
        before = day - timedelta(days=1)
        while not book.is_working(before) and (before - day).days > -15:
            before -= timedelta(days=1)
        after = day + timedelta(days=1)
        while not book.is_working(after) and (after - day).days < 15:
            after += timedelta(days=1)
        return leave_day(before) and leave_day(after)

    rows = []
    for day in date_range(start, end):
        kind = book.kind(day)
        if kind == "working":
            counted = Decimal("1")
        elif leave_type.sandwich_rule and sandwiched(day):
            counted, kind = Decimal("1"), "sandwich"
        else:
            counted = ZERO
        rows.append({"date": day, "kind": kind, "counted": counted, "label": book.holiday(day) or ""})

    if leave_type.sandwich_rule:
        # Off days just outside the range, between this leave and an existing one.
        for direction in (-1, 1):
            edge = start if direction < 0 else end
            if not book.is_working(edge):
                continue
            day = edge + timedelta(days=direction)
            run = []
            while not book.is_working(day) and len(run) < 14:
                run.append(day)
                day += timedelta(days=direction)
            if run and day in existing:
                for off in run:
                    rows.append(
                        {
                            "date": off,
                            "kind": "sandwich",
                            "counted": Decimal("1"),
                            "label": book.holiday(off) or "",
                        }
                    )
        rows.sort(key=lambda r: r["date"])
    return sum((r["counted"] for r in rows), ZERO), rows


# ---------------------------------------------------------------- validation
@dataclass
class Check:
    days: Decimal = ZERO
    breakdown: list = field(default_factory=list)
    errors: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    needs_document: bool = False
    needs_hr: bool = False
    available: Decimal | None = None

    def as_dict(self) -> dict:
        return {
            "days": float(self.days),
            "days_label": fmt_days(self.days),
            "breakdown": [
                {
                    "date": r["date"].isoformat(),
                    "kind": r["kind"],
                    "counted": float(r["counted"]),
                    "label": r["label"],
                }
                for r in self.breakdown
            ],
            "errors": self.errors,
            "warnings": self.warnings,
            "needs_document": self.needs_document,
            "needs_hr_approval": self.needs_hr,
            "available": None if self.available is None else float(self.available),
            "ok": not self.errors,
        }


def parse_input(employee, data: dict) -> tuple[LeaveType | None, date | None, date | None, str, dict]:
    errors = {}
    code = str(data.get("leave_type") or "").strip()
    leave_type = LeaveType.objects.filter(location=employee.location, code=code, active=True).first()
    if leave_type is None:
        errors["leave_type"] = "Choose a leave type available at your location."
    start = end = None
    try:
        start = date.fromisoformat(str(data.get("start") or ""))
    except ValueError:
        errors["start"] = "Choose a start date."
    try:
        end = date.fromisoformat(str(data.get("end") or data.get("start") or ""))
    except ValueError:
        errors["end"] = "Choose an end date."
    half = str(data.get("half") or "")
    if half not in HalfDay.values:
        errors["half"] = "Choose full day, first half or second half."
    return leave_type, start, end, half, errors


def check(employee, data: dict, *, today: date | None = None, has_document=False, exclude=None) -> Check:
    """Run every rule and return the day count, errors and team warnings. Never saves."""
    from .team import clash_warnings

    today = today or today_ist(timezone.now())
    result = Check()
    leave_type, start, end, half, errors = parse_input(employee, data)
    result.errors.update(errors)
    if errors:
        return result
    if end < start:
        result.errors["end"] = "The end date must be on or after the start date."
        return result
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        result.errors["end"] = f"Apply for at most {MAX_RANGE_DAYS} calendar days at a time."
        return result
    if start.year != end.year:
        result.errors["end"] = "Leave that crosses 31 December needs two requests, one for each year."
        return result
    if half:
        if not leave_type.half_day_allowed:
            result.errors["half"] = f"{leave_type.name} cannot be taken as a half day."
        elif start != end:
            result.errors["half"] = "A half day starts and ends on the same date."
        if result.errors:
            return result

    days, rows = count_days(employee, leave_type, start, end, half, exclude=exclude)
    result.days, result.breakdown = days, rows
    if days == 0:
        result.errors["start"] = "These dates are weekly offs or holidays, so there is nothing to apply for."
        return result

    if start < employee.joined_on:
        result.errors["start"] = f"Leave can start from your joining date, {nice_date(employee.joined_on)}."
    notice = (start - today).days
    if notice < 0:
        if -notice > leave_type.backdate_days:
            result.errors["start"] = (
                f"{leave_type.name} can be applied up to {leave_type.backdate_days} days after it was taken."
                if leave_type.backdate_days
                else "Leave cannot start in the past."
            )
    elif notice < leave_type.min_notice_days:
        result.errors["start"] = (
            f"{leave_type.name} needs {leave_type.min_notice_days} days' notice. "
            f"The earliest start is {nice_date(today + timedelta(days=leave_type.min_notice_days))}."
        )
    if leave_type.max_consecutive_days and days > leave_type.max_consecutive_days:
        result.errors["end"] = (
            f"{leave_type.name} allows at most {fmt_days(leave_type.max_consecutive_days)} in one request."
        )
    if leave_type.document_after_days is not None and days > leave_type.document_after_days:
        result.needs_document = True
        if not has_document:
            result.errors["document"] = (
                f"Attach a document (for example a medical certificate) for {leave_type.name.lower()} "
                f"longer than {fmt_days(leave_type.document_after_days)}."
            )

    clashes = LeaveRequest.objects.filter(employee=employee, status__in=OPEN, start__lte=end, end__gte=start)
    if exclude is not None:
        clashes = clashes.exclude(pk=exclude.pk)
    for other in clashes:
        if half and other.half and other.half != half and other.start == start:
            continue  # the other half of the same day
        result.errors["start"] = (
            f"You already have {other.leave_type.name.lower()} {other.get_status_display().lower()} "
            f"from {nice_date(other.start)} to {nice_date(other.end)}."
        )
        break

    if not leave_type.unpaid:
        left = available(employee, leave_type, start.year, today=today, month=start.month, exclude=exclude)
        result.available = left
        if days > left:
            result.errors["leave_type"] = (
                f"You have {fmt_days(max(left, ZERO))} of {leave_type.name.lower()} available"
                + (" for that date" if start.year > today.year else "")
                + f", and this request needs {fmt_days(days)}."
            )

    result.needs_hr = days > policy_for(employee.location).hr_approval_over_days
    result.warnings = clash_warnings(employee, [r["date"] for r in rows if r["counted"] > 0], exclude=exclude)
    return result


# ---------------------------------------------------------------- routing
def on_leave(employee, day: date) -> bool:
    return LeaveRequest.objects.filter(
        employee=employee, status=LeaveStatus.APPROVED, start__lte=day, end__gte=day, half=""
    ).exists()


_UNSET = object()


def chain_approver(employee, day: date, start_from=_UNSET) -> tuple[object | None, bool]:
    """(user, delegated). Walks up the reporting line from `start_from` (default: the manager),
    skipping people who are on leave today or inactive. None when the line runs out."""
    seen = {employee.id}
    candidate = employee.manager if start_from is _UNSET else start_from
    delegated = False
    while candidate is not None and candidate.id not in seen:
        seen.add(candidate.id)
        if candidate.user.is_active and not on_leave(candidate, day):
            return candidate.user, delegated
        delegated = True
        candidate = candidate.manager
    return None, delegated


def _log(leave, actor, action, detail=""):
    LeaveAction.objects.create(request=leave, actor=actor, action=action, detail=detail[:200])


def _notify_approver(leave, user):
    emp = leave.employee
    notify(
        user,
        kind="leave_approval",
        title=f"Leave to approve: {emp.name}, {fmt_days(leave.days)} from {nice_date(leave.start)}",
        body="Open your approvals to see the dates and the team calendar.",
        link="/leave/approvals",
    )


def _hr_people():
    from accounts.models import User

    return User.objects.filter(role=Role.HR, is_active=True)


def assign(leave, now, *, stage: str, start_from=_UNSET, reason="") -> None:
    day = today_ist(now)
    leave.stage, leave.assigned_at = stage, now
    if stage == ApprovalStage.MANAGER:
        approver, delegated = chain_approver(leave.employee, day, start_from)
        leave.approver = approver
        leave.delegated = leave.delegated or delegated
        if approver is None:
            leave.stage = ApprovalStage.HR  # nobody left in the reporting line
    else:
        leave.approver = None
    leave.save()
    if leave.approver is not None:
        _log(leave, None, "assigned", reason or f"Waiting for {leave.approver.full_name}")
        _notify_approver(leave, leave.approver)
    else:
        _log(leave, None, "assigned", reason or "Waiting for HR")
        for admin in _hr_people():
            if admin.id != leave.employee.user_id:
                _notify_approver(leave, admin)


def apply(employee, actor, data: dict, *, document=None, request=None, now=None) -> LeaveRequest:
    now = now or timezone.now()
    today = today_ist(now)
    with transaction.atomic():
        # One request at a time per person, so two quick submissions cannot both pass the balance check.
        Employee.objects.select_for_update().get(pk=employee.pk)
        result = check(employee, data, today=today, has_document=document is not None)
        if result.errors:
            raise ValidationError(result.errors)
        leave_type, start, end, half, _ = parse_input(employee, data)
        stored = None
        if document is not None:
            from files.storage import save_file

            stored = save_file(
                owner=actor, original_name=document[0], content_type=document[1], raw=document[2]
            )
        leave = LeaveRequest.objects.create(
            employee=employee,
            leave_type=leave_type,
            start=start,
            end=end,
            half=half,
            days=result.days,
            reason=str(data.get("reason") or "").strip()[:1000],
            document=stored,
        )
        _log(leave, actor, "submitted", f"{fmt_days(result.days)} of {leave_type.name.lower()}")
        assign(leave, now, stage=ApprovalStage.MANAGER)
    audit(request, "leave.applied", actor=actor, target=leave, days=str(leave.days), type=leave_type.code)
    return leave


def can_act(leave, user) -> bool:
    if leave.status != LeaveStatus.PENDING or leave.employee.user_id == user.id:
        return False
    if leave.approver_id is not None:
        return leave.approver_id == user.id or (leave.escalated and user.role == Role.HR)
    return user.role == Role.HR


def approvals_for(user):
    qs = LeaveRequest.objects.filter(status=LeaveStatus.PENDING).select_related(
        "employee", "employee__user", "employee__department", "leave_type", "approver"
    )
    mine = Q(approver=user)
    if user.role == Role.HR:
        mine |= Q(approver__isnull=True) | Q(escalated=True)
    return qs.filter(mine).exclude(employee__user=user).order_by("start")


def _finalise(leave, actor, now):
    leave.status, leave.decided_by, leave.decided_at = LeaveStatus.APPROVED, actor, now
    leave.stage, leave.approver = "", None
    leave.save()
    if not leave.leave_type.unpaid:
        _credit(
            leave.employee,
            leave.leave_type,
            leave.start.year,
            LedgerKind.USE,
            -leave.days,
            f"use:{leave.id}",
            f"{nice_date(leave.start)} to {nice_date(leave.end)}",
        )
    notify(
        leave.employee.user,
        kind="leave_decided",
        title=f"Leave approved: {nice_date(leave.start)}"
        + (f" to {nice_date(leave.end)}" if leave.end != leave.start else ""),
        body=f"{fmt_days(leave.days)} of {leave.leave_type.name.lower()} approved.",
        link="/leave",
    )


def approve(leave, actor, note: str = "", request=None, now=None) -> LeaveRequest:
    now = now or timezone.now()
    with transaction.atomic():
        leave = (
            LeaveRequest.objects.select_for_update()
            .select_related("employee", "employee__user", "employee__location", "leave_type")
            .get(pk=leave.pk)
        )
        if not can_act(leave, actor):
            raise PermissionDenied("This leave is not waiting for you.")
        leave.decision_note = (note or "").strip()[:500]
        needs_hr = leave.days > policy_for(leave.employee.location).hr_approval_over_days
        if leave.stage == ApprovalStage.MANAGER and needs_hr and actor.role != Role.HR:
            leave.manager_approved_by = actor
            leave.escalated = False
            _log(leave, actor, "approved", "Approved by the reporting manager; HR approval needed")
            assign(leave, now, stage=ApprovalStage.HR, reason="Longer than the HR threshold: waiting for HR")
        else:
            if leave.stage == ApprovalStage.MANAGER:
                leave.manager_approved_by = actor
            _log(leave, actor, "approved", "")
            _finalise(leave, actor, now)
    audit(request, "leave.approved", actor=actor, target=leave)
    return leave


def reject(leave, actor, note: str, request=None, now=None) -> LeaveRequest:
    now = now or timezone.now()
    if len((note or "").strip()) < 5:
        raise ValidationError({"note": "Tell the employee why (at least 5 characters)."})
    with transaction.atomic():
        leave = (
            LeaveRequest.objects.select_for_update()
            .select_related("employee", "employee__user", "leave_type")
            .get(pk=leave.pk)
        )
        if not can_act(leave, actor):
            raise PermissionDenied("This leave is not waiting for you.")
        leave.status, leave.decided_by, leave.decided_at = LeaveStatus.REJECTED, actor, now
        leave.decision_note = note.strip()[:500]
        leave.stage, leave.approver = "", None
        leave.save()
        _log(leave, actor, "rejected", "")
    notify(
        leave.employee.user,
        kind="leave_decided",
        title=f"Leave not approved: {nice_date(leave.start)}",
        body=f"{actor.full_name} did not approve this request: {leave.decision_note}",
        link="/leave",
    )
    audit(request, "leave.rejected", actor=actor, target=leave)
    return leave


def cancel(leave, actor, request=None, now=None) -> LeaveRequest:
    now = now or timezone.now()
    today = today_ist(now)
    with transaction.atomic():
        leave = (
            LeaveRequest.objects.select_for_update().select_related("employee", "leave_type").get(pk=leave.pk)
        )
        if leave.employee.user_id != actor.id:
            raise PermissionDenied("Only the employee can cancel their own leave.")
        if leave.status not in OPEN:
            raise ValidationError({"status": "This request is already closed."})
        if leave.start <= today:
            raise ValidationError({"status": "Leave can be cancelled only before its start date."})
        was_approved = leave.status == LeaveStatus.APPROVED
        approver = leave.approver
        leave.status, leave.stage, leave.approver = LeaveStatus.CANCELLED, "", None
        leave.save()
        _log(leave, actor, "cancelled", "")
        if was_approved and not leave.leave_type.unpaid:
            _credit(
                leave.employee,
                leave.leave_type,
                leave.start.year,
                LedgerKind.REVERSAL,
                leave.days,
                f"reversal:{leave.id}",
                "Cancelled before the start date",
            )
    if approver is not None:
        notify(
            approver,
            kind="leave_cancelled",
            title=f"Leave cancelled: {leave.employee.name}, {nice_date(leave.start)}",
            body="Nothing to approve any more.",
            link="/leave/approvals",
            email=False,
        )
    audit(request, "leave.cancelled", actor=actor, target=leave)
    return leave


# ---------------------------------------------------------------- delegation and escalation
def refresh_delegations(now=None) -> int:
    """Pending requests whose approver is now on leave move to that approver's manager."""
    now = now or timezone.now()
    day = today_ist(now)
    moved = 0
    for leave in LeaveRequest.objects.filter(
        status=LeaveStatus.PENDING, stage=ApprovalStage.MANAGER, approver__isnull=False
    ).select_related("approver", "employee"):
        approver_emp = Employee.objects.filter(user=leave.approver).select_related("manager").first()
        if approver_emp is None or not on_leave(approver_emp, day):
            continue
        leave.delegated = True
        assign(
            leave,
            now,
            stage=ApprovalStage.MANAGER,
            start_from=approver_emp.manager,
            reason=f"{leave.approver.full_name} is on leave: delegated",
        )
        moved += 1
    return moved


def escalate_due(now=None) -> int:
    """Pending longer than the location's limit (48 hours by default): up one level, and flagged."""
    now = now or timezone.now()
    moved = 0
    for leave in LeaveRequest.objects.filter(
        status=LeaveStatus.PENDING, assigned_at__isnull=False
    ).select_related("employee", "employee__location", "approver"):
        limit = timedelta(hours=policy_for(leave.employee.location).escalate_after_hours)
        if now - leave.assigned_at < limit:
            continue
        if leave.approver is None:  # already with HR: flag once
            if not leave.escalated:
                leave.escalated = True
                leave.save(update_fields=["escalated", "updated_at"])
                _log(leave, None, "escalated", "Waiting for HR for more than the escalation limit")
                moved += 1
            continue
        approver_emp = Employee.objects.filter(user=leave.approver).select_related("manager").first()
        previous = leave.approver.full_name
        leave.escalated = True
        _log(leave, None, "escalated", f"No answer from {previous}")
        assign(
            leave,
            now,
            stage=ApprovalStage.MANAGER,
            start_from=approver_emp.manager if approver_emp else None,
            reason=f"Escalated: no answer from {previous}",
        )
        moved += 1
    return moved


def needs_attention():
    """Escalated requests and those with nobody in the reporting line (for HR)."""
    return (
        LeaveRequest.objects.filter(status=LeaveStatus.PENDING)
        .filter(Q(escalated=True) | Q(approver__isnull=True))
        .select_related("employee", "employee__user", "leave_type", "approver")
    )


def as_datetime(day: date, hour=10) -> datetime:
    from interviews.timeutil import IST

    return datetime(day.year, day.month, day.day, hour, 0, tzinfo=IST)

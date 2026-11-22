"""Team calendar and clash warnings.

A team is the people who share a reporting manager. Peers see who is off and
when; only the team's manager (and hr_admin) see the leave type and reason.
"""

from datetime import date, timedelta

from accounts.models import Role

from .calendar_rules import DayBook, date_range, policy_for
from .models import Employee, LeaveRequest, LeaveStatus

OPEN = (LeaveStatus.PENDING, LeaveStatus.APPROVED)
MAX_WARNINGS = 4


def team_members(employee) -> list:
    if employee.manager_id is None:
        return [employee]
    return list(
        Employee.objects.filter(manager_id=employee.manager_id, user__is_active=True).select_related("user")
    )


def team_name(manager) -> str:
    return f"{manager.name}'s team" if manager else "Your team"


def _off_by_day(members, start: date, end: date, exclude_employee=None, exclude=None) -> dict:
    ids = [m.id for m in members if exclude_employee is None or m.id != exclude_employee.id]
    qs = LeaveRequest.objects.filter(employee_id__in=ids, status__in=OPEN, start__lte=end, end__gte=start)
    if exclude is not None:
        qs = qs.exclude(pk=exclude.pk)
    off: dict = {}
    for req in qs:
        for day in date_range(max(req.start, start), min(req.end, end)):
            off.setdefault(day, set()).add(req.employee_id)
    return off


def clash_warnings(employee, days: list, exclude=None) -> list[str]:
    """Warn (never block) when the team would drop below the location's availability threshold."""
    if not days:
        return []
    members = team_members(employee)
    size = len(members)
    if size < 2:
        return []
    pct = policy_for(employee.location).min_team_available_pct
    off = _off_by_day(members, min(days), max(days), exclude_employee=employee, exclude=exclude)
    label = team_name(employee.manager)
    out = []
    for day in sorted(days):
        already = len(off.get(day, ()))
        if already == 0:
            continue
        left = size - already - 1
        if left * 100 < pct * size:
            out.append(
                f"{already} of {size} people in {label} are already off on "
                f"{day.strftime('%a %d %b').replace(' 0', ' ')} ({left} would be available)."
            )
    if len(out) > MAX_WARNINGS:
        extra = len(out) - MAX_WARNINGS
        out = out[:MAX_WARNINGS] + [
            f"…and {extra} more day{'s' if extra > 1 else ''} below the team's threshold."
        ]
    return out


def manager_view_allowed(viewer_user, manager_employee) -> bool:
    return viewer_user.role == Role.HR_ADMIN or (
        manager_employee is not None and manager_employee.user_id == viewer_user.id
    )


def calendar(viewer_user, viewer_employee, month_start: date, *, team_of=None) -> dict:
    """team_of: the manager Employee whose reports to show. Defaults to the viewer's own team
    (people sharing the viewer's manager)."""
    if team_of is not None:
        manager = team_of
        members = list(
            Employee.objects.filter(manager=team_of, user__is_active=True).select_related("user")
        ) + [team_of]
        name = f"{team_of.name} and direct reports"
    else:
        manager = viewer_employee.manager
        members = team_members(viewer_employee)
        name = team_name(manager)
    sees_reasons = manager_view_allowed(viewer_user, manager) or (
        team_of is not None and team_of.user_id == viewer_user.id
    )
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    end = next_month - timedelta(days=1)
    location = viewer_employee.location if viewer_employee else members[0].location
    book = DayBook(location, month_start, end)
    days = [
        {"date": d.isoformat(), "kind": book.kind(d), "holiday": book.holiday(d) or ""}
        for d in date_range(month_start, end)
    ]
    member_ids = [m.id for m in members]
    entries = []
    for req in (
        LeaveRequest.objects.filter(
            employee_id__in=member_ids, status__in=OPEN, start__lte=end, end__gte=month_start
        )
        .select_related("employee", "employee__user", "leave_type")
        .order_by("start")
    ):
        own = req.employee.user_id == viewer_user.id
        detail = sees_reasons or own
        entries.append(
            {
                "id": str(req.id),
                "employee": str(req.employee_id),
                "name": req.employee.name,
                "start": req.start.isoformat(),
                "end": req.end.isoformat(),
                "half": req.half,
                "status": req.status,
                "type": req.leave_type.name if detail else None,
                "reason": req.reason if detail else None,
            }
        )
    joiners = [
        {"name": m.name, "joined_on": m.joined_on.isoformat(), "designation": m.designation}
        for m in members
        if month_start <= m.joined_on <= end
    ]
    return {
        "month": month_start.strftime("%Y-%m"),
        "team": {
            "name": name,
            "members": [
                {"id": str(m.id), "name": m.name, "designation": m.designation}
                for m in sorted(members, key=lambda m: m.name)
            ],
        },
        "sees_reasons": sees_reasons,
        "threshold_pct": policy_for(location).min_team_available_pct,
        "days": days,
        "entries": entries,
        "joiners": joiners,
    }

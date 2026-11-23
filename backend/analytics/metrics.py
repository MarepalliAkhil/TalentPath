"""Hiring and people analytics (week 4A). Definitions: docs/ANALYTICS.md.

Every number is computed here from real records; nothing is hard-coded. Each section is
returned in one shape the frontend draws as a chart, a table and a one-line summary:

    {"key", "title", "summary", "chart": {"type", "x", "series": [{"key", "label"}]} | None,
     "columns": [{"key", "label"}], "rows": [{...}], "note": str}

Scope: hr_admin sees every job; recruiters the jobs they created; hiring managers the jobs
they are assigned to (the same rule as the rest of the product). People analytics are
for hr_admin only.
"""

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.db.models import Q
from django.utils import timezone

from applications.models import Application, ApplicationEvent, Source
from applications.models import ApplicationStatus as S
from interviews.timeutil import IST, today_ist
from jobs.services import visible_jobs

STAGES = [S.APPLIED, S.SCREENING, S.INTERVIEW, S.OFFER, S.HIRED]
STAGE_LABELS = {s: S(s).label for s in STAGES}
DEFAULT_DAYS = 180


# ---------------------------------------------------------------- statistics
def percentile(values, p: float) -> float | None:
    """Linear interpolation between closest ranks (the common "type 7" definition):
    rank = (n - 1) * p on the sorted values. None for an empty list."""
    data = sorted(values)
    if not data:
        return None
    k = (len(data) - 1) * p
    lo, hi = math.floor(k), math.ceil(k)
    value = data[lo] + (data[hi] - data[lo]) * (k - lo)
    return round(value, 1)


def median(values) -> float | None:
    return percentile(values, 0.5)


def rate(part: int, whole: int) -> float | None:
    """Percentage with one decimal; None when there is nothing to divide by."""
    return round(100 * part / whole, 1) if whole else None


def fmt_pct(value) -> str:
    return "n/a" if value is None else f"{value:g}%"


def fmt_days(value) -> str:
    return "n/a" if value is None else f"{value:g} days"


def days_between(a: datetime, b: datetime) -> float:
    return (b - a).total_seconds() / 86400


# ---------------------------------------------------------------- filters
@dataclass
class Filters:
    start: date
    end: date
    department: str = ""  # department id

    @property
    def start_dt(self):
        return datetime.combine(self.start, time.min, tzinfo=IST)

    @property
    def end_dt(self):
        return datetime.combine(self.end + timedelta(days=1), time.min, tzinfo=IST)


def parse_filters(params) -> Filters:
    from rest_framework.exceptions import ValidationError

    today = today_ist(timezone.now())
    try:
        end = date.fromisoformat(params.get("to")) if params.get("to") else today
        start = (
            date.fromisoformat(params.get("from"))
            if params.get("from")
            else end - timedelta(days=DEFAULT_DAYS)
        )
    except ValueError as exc:
        raise ValidationError({"from": "Use dates like 2026-11-01."}) from exc
    if start > end:
        raise ValidationError({"from": "The start date must be on or before the end date."})
    if (end - start).days > 731:
        raise ValidationError({"from": "Choose at most two years."})
    return Filters(start=start, end=end, department=str(params.get("department") or ""))


def scoped_applications(user, f: Filters):
    jobs = visible_jobs(user, with_counts=False)
    if f.department:
        jobs = jobs.filter(department_id=f.department)
    return Application.objects.filter(job__in=jobs, created_at__gte=f.start_dt, created_at__lt=f.end_dt)


def section(key, title, summary, columns, rows, chart=None, note="") -> dict:
    return {
        "key": key,
        "title": title,
        "summary": summary,
        "chart": chart,
        "columns": [{"key": k, "label": label} for k, label in columns],
        "rows": rows,
        "note": note,
    }


# ---------------------------------------------------------------- hiring
def _histories(apps):
    """{application id: [(status, entered_at), ...]} in time order, Applied first."""
    events = defaultdict(list)
    for e in (
        ApplicationEvent.objects.filter(application__in=apps)
        .order_by("created_at")
        .values("application_id", "to_status", "created_at")
    ):
        events[e["application_id"]].append((e["to_status"], e["created_at"]))
    out = {}
    for app in apps:
        trail = events.get(app.id, [])
        if not trail or trail[0][0] != S.APPLIED:
            trail = [(S.APPLIED, app.created_at)] + trail
        out[app.id] = trail
    return out


def time_to_hire(apps, histories) -> dict:
    values = []
    for app in apps:
        hired = next((at for st, at in histories[app.id] if st == S.HIRED), None)
        if hired:
            values.append(days_between(app.created_at, hired))
    med, p80 = median(values), percentile(values, 0.8)
    summary = (
        f"Median time to hire is {fmt_days(med)} (80th percentile {fmt_days(p80)}) "
        f"across {len(values)} hires."
        if values
        else "No hires in this period yet."
    )
    rows = [
        {"measure": "Median", "days": med},
        {"measure": "80th percentile", "days": p80},
        {"measure": "Hires", "days": len(values)},
    ]
    return section("time_to_hire", "Time to hire", summary, [("measure", "Measure"), ("days", "Days")], rows)


def time_in_stage(apps, histories) -> dict:
    spans = defaultdict(list)
    for app in apps:
        trail = histories[app.id]
        for (stage, entered), (_, left) in zip(trail, trail[1:], strict=False):
            if stage in (S.APPLIED, S.SCREENING, S.INTERVIEW, S.OFFER):
                spans[stage].append(days_between(entered, left))
    rows = [
        {
            "stage": STAGE_LABELS[stage],
            "median": median(spans[stage]),
            "p80": percentile(spans[stage], 0.8),
            "count": len(spans[stage]),
        }
        for stage in (S.APPLIED, S.SCREENING, S.INTERVIEW, S.OFFER)
    ]
    slowest = max((r for r in rows if r["median"] is not None), key=lambda r: r["median"], default=None)
    summary = (
        f"Applications wait longest at {slowest['stage']}: median {fmt_days(slowest['median'])}."
        if slowest
        else "No stage changes in this period yet."
    )
    return section(
        "time_in_stage",
        "Time in each stage",
        summary,
        [
            ("stage", "Stage"),
            ("median", "Median days"),
            ("p80", "80th percentile days"),
            ("count", "Moves out"),
        ],
        rows,
        chart={
            "type": "bar",
            "x": "stage",
            "series": [{"key": "median", "label": "Median days"}, {"key": "p80", "label": "80th percentile"}],
        },
        note="Counts only time already spent: a stage is measured when the application leaves it.",
    )


def funnel(apps, histories) -> dict:
    reached = Counter()
    for app in apps:
        seen = {st for st, _ in histories[app.id]}
        for stage in STAGES:
            if stage in seen:
                reached[stage] += 1
    rows, prev = [], None
    for stage in STAGES:
        n = reached[stage]
        rows.append(
            {
                "stage": STAGE_LABELS[stage],
                "reached": n,
                "conversion": None if prev is None else rate(n, prev),
            }
        )
        prev = n
    total = reached[S.APPLIED]
    summary = (
        f"{total} applications: {rate(reached[S.INTERVIEW], total) if total else 0:g}% reached Interview and "
        f"{rate(reached[S.HIRED], total) if total else 0:g}% were hired."
        if total
        else "No applications in this period."
    )
    return section(
        "funnel",
        "Funnel conversion",
        summary,
        [("stage", "Stage"), ("reached", "Applications reaching it"), ("conversion", "% of previous stage")],
        rows,
        chart={"type": "bar", "x": "stage", "series": [{"key": "reached", "label": "Applications"}]},
    )


def sources(apps, histories) -> dict:
    rows = []
    for value, label in Source.choices:
        group = [a for a in apps if a.source == value]
        interviewed = sum(1 for a in group if any(st == S.INTERVIEW for st, _ in histories[a.id]))
        hired = sum(1 for a in group if any(st == S.HIRED for st, _ in histories[a.id]))
        rows.append(
            {
                "source": label,
                "applications": len(group),
                "interview_rate": rate(interviewed, len(group)),
                "hire_rate": rate(hired, len(group)),
            }
        )
    best = max(
        (r for r in rows if r["applications"] >= 5), key=lambda r: r["interview_rate"] or 0, default=None
    )
    summary = (
        f"{best['source']} gives the highest interview rate ({fmt_pct(best['interview_rate'])}) "
        "among sources with at least 5 applications."
        if best
        else "Not enough applications per source yet."
    )
    return section(
        "sources",
        "Source effectiveness",
        summary,
        [
            ("source", "Source"),
            ("applications", "Applications"),
            ("interview_rate", "% reaching Interview"),
            ("hire_rate", "% hired"),
        ],
        rows,
        chart={"type": "bar", "x": "source", "series": [{"key": "applications", "label": "Applications"}]},
    )


def offers(apps) -> dict:
    from offers.models import Offer, OfferStatus

    qs = list(Offer.objects.filter(application__in=apps).exclude(status__in=[OfferStatus.DRAFT]))
    counts = Counter(o.status for o in qs)
    accepted, declined, expired = (
        counts[OfferStatus.ACCEPTED],
        counts[OfferStatus.DECLINED],
        counts[OfferStatus.EXPIRED],
    )
    # A hire keeps the offer "accepted", so hired offers are counted as accepted here.
    acceptance = rate(accepted, accepted + declined + expired)
    reasons = Counter(
        (o.decline_reason or "No reason given").strip()[:80] for o in qs if o.status == OfferStatus.DECLINED
    )
    rows = [{"outcome": OfferStatus(k).label, "offers": v} for k, v in sorted(counts.items())]
    rows += [{"outcome": f"Declined: {reason}", "offers": n} for reason, n in reasons.most_common()]
    summary = (
        f"Offer acceptance rate is {fmt_pct(acceptance)} "
        f"({accepted} accepted, {declined} declined, {expired} expired)."
        if accepted + declined + expired
        else "No offers have been answered in this period."
    )
    return section(
        "offers",
        "Offers: acceptance and decline reasons",
        summary,
        [("outcome", "Outcome"), ("offers", "Offers")],
        rows,
        note="Acceptance rate = accepted / (accepted + declined + expired).",
    )


def interviewer_load(apps) -> dict:
    from interviews.models import Interview, InterviewAssignment, Scorecard

    interviews = Interview.objects.filter(application__in=apps).exclude(status="cancelled")
    assignments = InterviewAssignment.objects.filter(
        interview__in=interviews, status="assigned"
    ).select_related("interviewer", "interview")
    cards = {
        (c.interview_id, c.interviewer_id): c.submitted_at
        for c in Scorecard.objects.filter(interview__in=interviews)
    }
    per = defaultdict(lambda: {"interviews": 0, "due": 0, "on_time": 0, "hours": []})
    now = timezone.now()
    for a in assignments:
        row = per[a.interviewer.full_name]
        row["interviews"] += 1
        iv = a.interview
        if iv.status == "completed" and iv.scorecard_due_at and iv.scorecard_due_at <= now:
            row["due"] += 1
            submitted = cards.get((iv.id, a.interviewer_id))
            if submitted and submitted <= iv.scorecard_due_at:
                row["on_time"] += 1
            if submitted and iv.ends_at:
                row["hours"].append((submitted - iv.ends_at).total_seconds() / 3600)
    rows = sorted(
        (
            {
                "interviewer": name,
                "interviews": v["interviews"],
                "scorecards_due": v["due"],
                "on_time": rate(v["on_time"], v["due"]),
                "median_hours": median(v["hours"]),
            }
            for name, v in per.items()
        ),
        key=lambda r: (-r["interviews"], r["interviewer"]),
    )
    due = sum(r["scorecards_due"] for r in rows)
    on_time = sum(per[r["interviewer"]]["on_time"] for r in rows)
    summary = (
        f"{len(rows)} interviewers; {fmt_pct(rate(on_time, due))} of {due} due scorecards "
        "arrived on time (within 24 hours)."
        if rows
        else "No interviews in this period."
    )
    return section(
        "interviewer_load",
        "Interviewer load and scorecard timeliness",
        summary,
        [
            ("interviewer", "Interviewer"),
            ("interviews", "Interviews"),
            ("scorecards_due", "Scorecards due"),
            ("on_time", "% on time"),
            ("median_hours", "Median hours to submit"),
        ],
        rows,
        chart={"type": "bar", "x": "interviewer", "series": [{"key": "interviews", "label": "Interviews"}]},
    )


def hira_automation(user, f: Filters, apps) -> dict:
    from hira.models import HiraAction, HiraActivity

    jobs = visible_jobs(user, with_counts=False)
    if f.department:
        jobs = jobs.filter(department_id=f.department)
    qs = HiraActivity.objects.filter(created_at__gte=f.start_dt, created_at__lt=f.end_dt).filter(
        Q(job__in=jobs) | Q(application__in=apps)
    )
    counts = Counter(qs.values_list("action", flat=True))
    wanted = [
        (HiraAction.INTERVIEW_SCHEDULED, "Interviews scheduled"),
        (HiraAction.RESCHEDULE_HANDLED, "Reschedules handled"),
        (HiraAction.SCORECARD_CHASED, "Feedback chased"),
        (HiraAction.REMINDER_SENT, "Reminders sent"),
        (HiraAction.INTERVIEWER_REPLACED, "Interviewers replaced"),
    ]
    rows = [{"action": label, "count": counts[action]} for action, label in wanted]
    needs_you = qs.filter(needs_you=True).count()
    rows.append({"action": "Needs-you items raised", "count": needs_you})
    summary = (
        f"HIRA scheduled {counts[HiraAction.INTERVIEW_SCHEDULED]} interviews, handled "
        f"{counts[HiraAction.RESCHEDULE_HANDLED]} reschedules and chased feedback "
        f"{counts[HiraAction.SCORECARD_CHASED]} "
        f"times; {needs_you} items needed a person."
    )
    return section(
        "hira",
        "HIRA automation",
        summary,
        [("action", "Action"), ("count", "Count")],
        rows,
        chart={"type": "bar", "x": "action", "series": [{"key": "count", "label": "Count"}]},
    )


def match_vs_outcome(apps, histories) -> dict:
    from matching.services import BAND_LABELS
    from matching.weights import BANDS

    by_band = defaultdict(list)
    for app in apps:
        fit = getattr(app, "fit_score", None)
        if fit is not None:
            by_band[fit.band].append(app)
    rows = []
    for _, key, label in BANDS:
        group = by_band.get(key, [])
        reached = [{st for st, _ in histories[a.id]} for a in group]
        rows.append(
            {
                "band": BAND_LABELS.get(key, label),
                "applications": len(group),
                "reached_interview": rate(sum(1 for r in reached if S.INTERVIEW in r), len(group)),
                "reached_offer": rate(sum(1 for r in reached if S.OFFER in r or S.HIRED in r), len(group)),
            }
        )
    top, low = rows[0], rows[-1]
    summary = (
        f"On this synthetic data, {fmt_pct(top['reached_interview'])} of {top['band']} "
        "matches reached Interview, "
        f"against {fmt_pct(low['reached_interview'])} of {low['band']} matches."
    )
    return section(
        "match_vs_outcome",
        "Match score versus outcome (synthetic data)",
        summary,
        [
            ("band", "Fit band"),
            ("applications", "Applications"),
            ("reached_interview", "% reaching Interview"),
            ("reached_offer", "% reaching Offer"),
        ],
        rows,
        chart={
            "type": "bar",
            "x": "band",
            "series": [
                {"key": "reached_interview", "label": "% reaching Interview"},
                {"key": "reached_offer", "label": "% reaching Offer"},
            ],
        },
        note="Synthetic demo data: the seed moves candidates through stages, so this shows the mechanics, "
        "not evidence that the score predicts hiring outcomes.",
    )


def hiring_report(user, f: Filters) -> list[dict]:
    apps = list(scoped_applications(user, f).select_related("fit_score", "job"))
    histories = _histories(apps)
    return [
        time_to_hire(apps, histories),
        time_in_stage(apps, histories),
        funnel(apps, histories),
        sources(apps, histories),
        offers(apps),
        interviewer_load(apps),
        hira_automation(user, f, apps),
        match_vs_outcome(apps, histories),
    ]


# ---------------------------------------------------------------- people (hr_admin)
def _employees(f: Filters):
    from hr.models import Employee

    qs = Employee.objects.select_related("location", "department", "user").filter(user__is_active=True)
    if f.department:
        qs = qs.filter(department_id=f.department)
    return list(qs)


def leave_utilisation(f: Filters, employees) -> dict:
    from hr.models import LeaveLedger, LeaveRequest, LeaveStatus, LeaveType, LedgerKind

    year = f.end.year
    ids = [e.id for e in employees]
    credited = defaultdict(float)
    for row in LeaveLedger.objects.filter(
        employee_id__in=ids,
        year=year,
        kind__in=[LedgerKind.GRANT, LedgerKind.ACCRUAL, LedgerKind.CARRY, LedgerKind.ADJUST],
    ).values("leave_type__code", "days"):
        credited[row["leave_type__code"]] += float(row["days"])
    taken = defaultdict(float)
    for row in LeaveRequest.objects.filter(
        employee_id__in=ids, status=LeaveStatus.APPROVED, start__year=year
    ).values("leave_type__code", "days"):
        taken[row["leave_type__code"]] += float(row["days"])
    names = dict(LeaveType.objects.values_list("code", "name").distinct())
    rows = [
        {
            "type": names.get(code, code),
            "credited": round(credited.get(code, 0.0), 1),
            "taken": round(taken.get(code, 0.0), 1),
            "utilisation": rate(taken.get(code, 0.0), credited.get(code, 0.0))
            if credited.get(code)
            else None,
        }
        for code in sorted(set(credited) | set(taken) | set(names))
    ]
    used = [r for r in rows if r["utilisation"] is not None]
    top = max(used, key=lambda r: r["utilisation"], default=None)
    summary = (
        f"In {year}, {top['type'].lower()} is the most used: "
        f"{fmt_pct(top['utilisation'])} of the days credited so far."
        if top
        else f"No leave credited in {year} yet."
    )
    return section(
        "leave_utilisation",
        f"Leave utilisation by type ({year})",
        summary,
        [
            ("type", "Leave type"),
            ("credited", "Days credited"),
            ("taken", "Days taken (approved)"),
            ("utilisation", "% used"),
        ],
        rows,
        chart={
            "type": "bar",
            "x": "type",
            "series": [{"key": "credited", "label": "Credited"}, {"key": "taken", "label": "Taken"}],
        },
        note="Loss of pay has no credit, so it shows days taken only.",
    )


def _weekly_attendance(f: Filters, employees):
    """Per ISO week: working person-days, check-ins, late check-ins and absences. Only days on or
    after the first recorded check-in count, so weeks before attendance tracking began are left out."""
    from hr.calendar_rules import DayBook, date_range
    from hr.models import AttendanceRecord, LeaveRequest, LeaveStatus

    ids = [e.id for e in employees]
    first = (
        AttendanceRecord.objects.filter(employee_id__in=ids, check_in__isnull=False)
        .order_by("date")
        .values_list("date", flat=True)
        .first()
    )
    today = today_ist(timezone.now())
    if first is None:
        return []
    start, end = max(f.start, first), min(f.end, today - timedelta(days=1))
    if start > end:
        return []
    records = {
        (r.employee_id, r.date): r
        for r in AttendanceRecord.objects.filter(employee_id__in=ids, date__gte=start, date__lte=end)
    }
    leave = set()
    for req in LeaveRequest.objects.filter(
        employee_id__in=ids, status=LeaveStatus.APPROVED, start__lte=end, end__gte=start
    ):
        for d in date_range(max(req.start, start), min(req.end, end)):
            leave.add((req.employee_id, d))
    books = {}
    weeks = defaultdict(lambda: {"working": 0, "present": 0, "late": 0, "absent": 0})
    for emp in employees:
        book = books.get(emp.location_id) or books.setdefault(
            emp.location_id, DayBook(emp.location, start, end)
        )
        for d in date_range(max(start, emp.joined_on), end):
            if not book.is_working(d):
                continue
            week = d - timedelta(days=d.weekday())
            row = weeks[week]
            rec = records.get((emp.id, d))
            if rec and rec.check_in:
                row["working"] += 1
                row["present"] += 1
                row["late"] += int(rec.late)
            elif (emp.id, d) in leave:
                continue  # planned leave is neither present nor absent
            else:
                row["working"] += 1
                row["absent"] += 1
    return sorted(weeks.items())


def absenteeism(weeks) -> dict:
    rows = [
        {
            "week": wk.isoformat(),
            "absence_rate": rate(v["absent"], v["working"]),
            "absent_days": v["absent"],
            "working_days": v["working"],
        }
        for wk, v in weeks
    ]
    total_abs, total_work = sum(r["absent_days"] for r in rows), sum(r["working_days"] for r in rows)
    summary = (
        f"Unplanned absence is {fmt_pct(rate(total_abs, total_work))} of {total_work} working person-days "
        f"over {len(rows)} weeks."
        if rows
        else "No attendance recorded in this period."
    )
    return section(
        "absenteeism",
        "Absenteeism trend (weekly)",
        summary,
        [
            ("week", "Week starting"),
            ("absence_rate", "% absent"),
            ("absent_days", "Days absent"),
            ("working_days", "Working person-days"),
        ],
        rows,
        chart={"type": "line", "x": "week", "series": [{"key": "absence_rate", "label": "% absent"}]},
        note="Absent = a working day with no check-in and no approved leave. "
        "Days before attendance tracking began are not counted.",
    )


def late_trend(weeks) -> dict:
    rows = [
        {
            "week": wk.isoformat(),
            "late_rate": rate(v["late"], v["present"]),
            "late": v["late"],
            "check_ins": v["present"],
        }
        for wk, v in weeks
    ]
    late, check_ins = sum(r["late"] for r in rows), sum(r["check_ins"] for r in rows)
    summary = (
        f"{fmt_pct(rate(late, check_ins))} of {check_ins} check-ins were late "
        "(after the shift start plus grace)."
        if rows
        else "No check-ins in this period."
    )
    return section(
        "late_trend",
        "Late check-in trend (weekly)",
        summary,
        [
            ("week", "Week starting"),
            ("late_rate", "% late"),
            ("late", "Late check-ins"),
            ("check_ins", "Check-ins"),
        ],
        rows,
        chart={"type": "line", "x": "week", "series": [{"key": "late_rate", "label": "% late"}]},
    )


def onboarding(f: Filters, employees) -> dict:
    from hr.models import OnboardingTask

    ids = [e.id for e in employees]
    tasks = list(
        OnboardingTask.objects.filter(employee_id__in=ids).values("employee_id", "done_at", "due_on")
    )
    today = today_ist(timezone.now())
    per = defaultdict(lambda: [0, 0])
    overdue = 0
    for t in tasks:
        per[t["employee_id"]][0] += 1
        if t["done_at"]:
            per[t["employee_id"]][1] += 1
        elif t["due_on"] < today:
            overdue += 1
    complete = sum(1 for total, done in per.values() if total and total == done)
    done_tasks = sum(d for _, d in per.values())
    rows = [
        {"measure": "Joiners with a checklist", "value": len(per)},
        {"measure": "Checklists complete", "value": complete},
        {"measure": "Completion rate (%)", "value": rate(complete, len(per))},
        {"measure": "Tasks done", "value": done_tasks},
        {"measure": "Tasks overdue", "value": overdue},
    ]
    summary = (
        f"{complete} of {len(per)} onboarding checklists are complete ({fmt_pct(rate(complete, len(per)))}); "
        f"{overdue} tasks are overdue."
        if per
        else "No onboarding checklists yet."
    )
    return section(
        "onboarding", "Onboarding completion", summary, [("measure", "Measure"), ("value", "Value")], rows
    )


def mobility(f: Filters, employees) -> dict:
    from hr.models import InternalMove

    ids = [e.id for e in employees]
    moves = list(
        InternalMove.objects.filter(
            employee_id__in=ids, moved_on__gte=f.start, moved_on__lte=f.end
        ).select_related("employee__user")
    )
    rows = [
        {
            "moved_on": m.moved_on.isoformat(),
            "employee": m.employee.name,
            "from": f"{m.from_designation}, {m.from_department}",
            "to": f"{m.to_designation}, {m.to_department}",
        }
        for m in moves
    ]
    from applications.models import Application

    internal = Application.objects.filter(
        source=Source.INTERNAL, created_at__gte=f.start_dt, created_at__lt=f.end_dt
    )
    if f.department:
        internal = internal.filter(job__department_id=f.department)
    summary = f"{len(moves)} internal moves and {internal.count()} internal applications in this period."
    return section(
        "mobility",
        "Internal mobility moves",
        summary,
        [("moved_on", "Date"), ("employee", "Employee"), ("from", "From"), ("to", "To")],
        rows,
    )


def people_report(f: Filters) -> list[dict]:
    employees = _employees(f)
    weeks = _weekly_attendance(f, employees)
    return [
        leave_utilisation(f, employees),
        absenteeism(weeks),
        late_trend(weeks),
        onboarding(f, employees),
        mobility(f, employees),
    ]

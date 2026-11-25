"""HIRA's activity log, the login briefing and the "Needs you" list.

Every HIRA action is written here (append-only) and mirrored to the audit log.
Briefing counts come from this log only. "Needs you" items are log rows marked
needs_you whose problem is still open in the data (checked on read), so an item
disappears by itself once someone fixes it.
"""

from collections import Counter
from datetime import timedelta

from django.utils import timezone

from accounts.models import Role
from core.audit import audit

from .models import NEEDS_YOU_ACTIONS, BriefingState, HiraAction, HiraActivity

DEFAULT_LOOKBACK = timedelta(days=7)
# Which counts the briefing reports, in this order.
BRIEFING_COUNTS = [
    (HiraAction.INTERVIEW_SCHEDULED, "scheduled {n} interview{s}"),
    (HiraAction.RESCHEDULE_HANDLED, "handled {n} reschedule{s}"),
    (HiraAction.INTERVIEWER_REPLACED, "replaced {n} interviewer{s}"),
    (HiraAction.SCORECARD_CHASED, "chased {n} overdue scorecard{s}"),
    (HiraAction.REMINDER_SENT, "sent {n} reminder{s}"),
]
ATTENTION_FOR = {
    HiraAction.NO_SLOTS: "no_slots",
    HiraAction.REPLACEMENT_FAILED: "replacement_failed",
    HiraAction.RESCHEDULE_LIMIT: "reschedule_limit",
}


def log(
    action: str,
    *,
    job=None,
    application=None,
    interview=None,
    subject_user=None,
    reason_code: str = "",
    before: dict | None = None,
    after: dict | None = None,
    at=None,
) -> HiraActivity:
    if interview is not None and application is None:
        application = interview.application
    if application is not None and job is None:
        job = application.job
    row = HiraActivity.objects.create(
        action=action,
        job=job,
        application=application,
        interview=interview,
        subject_user=subject_user,
        reason_code=reason_code,
        before=before or {},
        after=after or {},
        needs_you=action in NEEDS_YOU_ACTIONS,
        created_at=at or timezone.now(),
    )
    target = interview or application or job
    audit(None, f"hira.{action}", target=target, reason=reason_code or None)
    return row


def scoped(user):
    qs = HiraActivity.objects.select_related("job", "application", "interview", "interview__round")
    if user.role == Role.HR:
        return qs
    if user.role == Role.RECRUITER:
        return qs.filter(job__created_by=user)
    return qs.none()


def _still_open(row: HiraActivity) -> bool:
    interview = row.interview
    if interview is None:
        return False
    if row.action in ATTENTION_FOR:
        return interview.attention == ATTENTION_FOR[row.action] and interview.status in (
            "pending",
            "scheduled",
        )
    if row.action == HiraAction.SCORECARD_OVERDUE:
        if interview.status != "completed" or row.subject_user_id is None:
            return False
        assigned = interview.assignments.filter(
            interviewer_id=row.subject_user_id, status="assigned"
        ).exists()
        submitted = interview.scorecards.filter(interviewer_id=row.subject_user_id).exists()
        return assigned and not submitted
    return False


def candidate_label(application) -> str:
    from applications.blind import is_blind

    if application is None:
        return ""
    return application.candidate_code if is_blind(application) else application.candidate.full_name


def item_dict(row: HiraActivity) -> dict:
    interview = row.interview
    job = row.job
    return {
        "id": str(row.id),
        "action": row.action,
        "label": HiraAction(row.action).label,
        "reason_code": row.reason_code,
        "job": {"id": str(job.id), "title": job.title} if job else None,
        "application": str(row.application_id) if row.application_id else None,
        "candidate": candidate_label(row.application),
        "interview": str(interview.id) if interview else None,
        "round": interview.round.name if interview else "",
        "created_at": row.created_at.isoformat(),
        "link": f"/recruiter/jobs/{job.id}/applications?open={row.application_id}" if job else "",
    }


def needs_you(user) -> list[HiraActivity]:
    seen, out = set(), []
    for row in scoped(user).filter(needs_you=True).order_by("-created_at"):
        key = (row.action, row.interview_id, row.subject_user_id)
        if key in seen:
            continue
        seen.add(key)
        if _still_open(row):
            out.append(row)
    return out


def _plural(template: str, n: int) -> str:
    return template.format(n=n, s="" if n == 1 else "s")


def briefing_message(counts: dict, needs: int) -> str:
    """Counts only: never names, so it is safe to read aloud."""
    parts = [_plural(t, counts.get(a, 0)) for a, t in BRIEFING_COUNTS if counts.get(a, 0)]
    if parts:
        text = "While you were away, HIRA " + (
            ", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else parts[0]
        )
    else:
        text = "While you were away, HIRA had nothing new to report"
    if needs:
        text += f"; {needs} item{'s' if needs != 1 else ''} need{'s' if needs == 1 else ''} you."
    else:
        text += "; nothing needs you right now."
    return text


def briefing(user, now=None) -> dict:
    now = now or timezone.now()
    state = BriefingState.objects.filter(user=user).first()
    since = state.last_seen_at if state else now - DEFAULT_LOOKBACK
    counts = Counter(scoped(user).filter(created_at__gt=since).values_list("action", flat=True))
    items = needs_you(user)
    message = briefing_message(counts, len(items))
    return {
        "since": since.isoformat(),
        "counts": {a.value: counts.get(a, 0) for a, _ in BRIEFING_COUNTS},
        "needs_you_count": len(items),
        "needs_you": [item_dict(r) for r in items[:5]],
        "message": message,
        "spoken": message,
    }


def mark_seen(user, now=None) -> None:
    BriefingState.objects.update_or_create(user=user, defaults={"last_seen_at": now or timezone.now()})


CHART_GROUPS = {
    "scheduled": (HiraAction.INTERVIEW_SCHEDULED,),
    "rescheduled": (HiraAction.RESCHEDULE_HANDLED, HiraAction.INTERVIEWER_REPLACED),
    "chased": (HiraAction.SCORECARD_CHASED,),
    "reminders": (HiraAction.REMINDER_SENT,),
    "needs_you": NEEDS_YOU_ACTIONS,
}


def summary(user, days: int = 14, now=None) -> dict:
    """KPI tiles and actions-by-day (IST dates) for the last `days` days."""
    from interviews.timeutil import ist

    now = now or timezone.now()
    start = now - timedelta(days=days)
    rows = list(scoped(user).filter(created_at__gte=start).values_list("action", "created_at"))
    by_action = Counter(a for a, _ in rows)
    today = ist(now).date()
    dates = [today - timedelta(days=offset) for offset in range(days - 1, -1, -1)]
    series = {d: {g: 0 for g in CHART_GROUPS} for d in dates}
    for action, at in rows:
        day = ist(at).date()
        if day not in series:
            continue
        for group, actions in CHART_GROUPS.items():
            if action in actions:
                series[day][group] += 1
    open_items = needs_you(user)
    return {
        "days": days,
        "kpis": {
            "actions": len(rows),
            "scheduled": by_action.get(HiraAction.INTERVIEW_SCHEDULED, 0),
            "reschedules": by_action.get(HiraAction.RESCHEDULE_HANDLED, 0),
            "replacements": by_action.get(HiraAction.INTERVIEWER_REPLACED, 0),
            "chased": by_action.get(HiraAction.SCORECARD_CHASED, 0),
            "reminders": by_action.get(HiraAction.REMINDER_SENT, 0),
            "needs_you": len(open_items),
        },
        "by_day": [{"date": d.isoformat(), **series[d]} for d in dates],
        "needs_you": [item_dict(r) for r in open_items],
        "actions": [{"value": a.value, "label": a.label} for a in HiraAction],
    }


def row_dict(row: HiraActivity) -> dict:
    return {
        **item_dict(row),
        "needs_you": row.needs_you,
        "before": row.before,
        "after": row.after,
    }

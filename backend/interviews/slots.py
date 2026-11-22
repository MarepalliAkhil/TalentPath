"""Deterministic slot finding for HIRA.

A slot is offered only when every required interviewer and the candidate are
free: inside each interviewer's working hours (IST), not blocked, and with no
active interview or unexpired hold. Panels need common free time. Interviewers
with the fewest interviews in that week are chosen first (ties: fewer
interviews overall, then a stable id order), so the load stays balanced.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from django.db.models import Q
from django.utils import timezone

from . import rules
from .models import (
    AssignmentStatus,
    BlockedTime,
    ClaimKind,
    InterviewAssignment,
    InterviewStatus,
    TimeClaim,
    default_working_hours,
)
from .timeutil import IST, ceil_to_grid, parse_hhmm, week_bounds


@dataclass(frozen=True)
class Slot:
    starts_at: datetime
    ends_at: datetime
    interviewer_ids: tuple[str, ...]


def live_claims(person_ids, start: datetime, end: datetime, now: datetime | None = None):
    """Claims that block time: active, overlapping, and not an expired hold."""
    now = now or timezone.now()
    return TimeClaim.objects.filter(
        person_id__in=list(person_ids), active=True, starts_at__lt=end, ends_at__gt=start
    ).exclude(kind=ClaimKind.HOLD, expires_at__lte=now)


def busy_map(
    person_ids, start: datetime, end: datetime, now: datetime | None = None, ignore_interview=None
) -> dict:
    """person id (str) -> list of (start, end) busy intervals in the window."""
    busy: dict[str, list] = defaultdict(list)
    claims = live_claims(person_ids, start, end, now)
    if ignore_interview is not None:
        claims = claims.exclude(interview=ignore_interview)
    for person_id, s, e in claims.values_list("person_id", "starts_at", "ends_at"):
        busy[str(person_id)].append((s, e))
    for user_id, s, e in BlockedTime.objects.filter(
        user_id__in=list(person_ids), starts_at__lt=end, ends_at__gt=start
    ).values_list("user_id", "starts_at", "ends_at"):
        busy[str(user_id)].append((s, e))
    return busy


def overlaps(intervals, start: datetime, end: datetime) -> bool:
    return any(s < end and e > start for s, e in intervals)


def working_hours(user) -> dict:
    profile = getattr(user, "interviewer_profile", None)
    try:
        return profile.working_hours if profile is not None else default_working_hours()
    except AttributeError:
        return default_working_hours()


def within_hours(hours: dict, start: datetime, end: datetime) -> bool:
    """The whole interval sits inside that weekday's working hours (IST), on one day."""
    local_start, local_end = start.astimezone(IST), end.astimezone(IST)
    if local_start.date() != local_end.date():
        return False
    window = hours.get(str(local_start.isoweekday()))
    if not window:
        return False
    return parse_hhmm(window[0]) <= local_start.time() and local_end.time() <= parse_hhmm(window[1])


def interview_counts(user_ids, start: datetime | None = None, end: datetime | None = None) -> dict:
    """Interviews per interviewer (scheduled or completed), optionally within [start, end)."""
    qs = InterviewAssignment.objects.filter(
        interviewer_id__in=list(user_ids),
        status=AssignmentStatus.ASSIGNED,
        interview__status__in=[InterviewStatus.SCHEDULED, InterviewStatus.COMPLETED],
    )
    if start is not None:
        qs = qs.filter(interview__starts_at__gte=start, interview__starts_at__lt=end)
    counts: dict[str, int] = defaultdict(int)
    for user_id in qs.values_list("interviewer_id", flat=True):
        counts[str(user_id)] += 1
    return counts


class LoadBook:
    """Caches weekly and total interview counts for load balancing."""

    def __init__(self, user_ids):
        self.user_ids = [str(u) for u in user_ids]
        self.total = interview_counts(self.user_ids)
        self.weeks: dict = {}

    def week(self, when: datetime) -> dict:
        start, end = week_bounds(when)
        if start not in self.weeks:
            self.weeks[start] = interview_counts(self.user_ids, start, end)
        return self.weeks[start]

    def order(self, user_ids, when: datetime) -> list[str]:
        week = self.week(when)
        return sorted(user_ids, key=lambda u: (week.get(u, 0), self.total.get(u, 0), u))


def eligible_pool(round_):
    """Pool members who are active users with an active (or no) interviewer profile."""
    users = (
        round_.pool.filter(is_active=True)
        .select_related("interviewer_profile")
        .filter(Q(interviewer_profile__isnull=True) | Q(interviewer_profile__active=True))
    )
    return list(users)


def find_slots(
    round_,
    candidate,
    *,
    now: datetime | None = None,
    max_slots: int = rules.MAX_SLOTS,
    avoid_starts=(),
    exclude_users=(),
    ignore_interview=None,
) -> list[Slot]:
    now = now or timezone.now()
    need = max(1, round_.interviewers_needed)
    pool = [u for u in eligible_pool(round_) if str(u.id) not in {str(x) for x in exclude_users}]
    if len(pool) < need:
        return []
    duration = timedelta(minutes=round_.duration_minutes)
    first = ceil_to_grid(now + rules.MIN_LEAD, rules.GRID_MINUTES)
    horizon_end = first + timedelta(days=rules.HORIZON_DAYS)
    ids = [str(u.id) for u in pool]
    busy = busy_map([*ids, str(candidate.id)], first, horizon_end + duration, now, ignore_interview)
    hours = {str(u.id): working_hours(u) for u in pool}
    loads = LoadBook(ids)
    avoid = {a.astimezone(IST) for a in avoid_starts}

    found: list[Slot] = []
    per_day: dict = defaultdict(list)
    step = timedelta(minutes=rules.GRID_MINUTES)
    start = first
    while start < horizon_end and len(found) < max_slots:
        end = start + duration
        day = start.date()
        day_slots = per_day[day]
        spaced = len(day_slots) < rules.MAX_SLOTS_PER_DAY and all(
            abs(start - s) >= rules.MIN_GAP_SAME_DAY for s in day_slots
        )
        if spaced and start not in avoid and not overlaps(busy[str(candidate.id)], start, end):
            free = [
                u for u in ids if within_hours(hours[u], start, end) and not overlaps(busy[u], start, end)
            ]
            if len(free) >= need:
                chosen = tuple(loads.order(free, start)[:need])
                found.append(Slot(start.astimezone(UTC), end.astimezone(UTC), chosen))
                day_slots.append(start)
        start += step
    return found


def free_replacements(
    round_, start: datetime, end: datetime, *, exclude_users=(), ignore_interview=None
) -> list[str]:
    """Pool members free for [start, end), best balanced first."""
    excluded = {str(x) for x in exclude_users}
    pool = [u for u in eligible_pool(round_) if str(u.id) not in excluded]
    ids = [str(u.id) for u in pool]
    busy = busy_map(ids, start, end, ignore_interview=ignore_interview)
    free = [
        str(u.id)
        for u in pool
        if within_hours(working_hours(u), start, end) and not overlaps(busy[str(u.id)], start, end)
    ]
    return LoadBook(ids).order(free, start)

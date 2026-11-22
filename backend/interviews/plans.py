"""Editing a job's interview plan and an interviewer's availability (validation lives here)."""

import re
from datetime import datetime, timedelta

from django.db import transaction
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError

from accounts.models import Role, User

from .models import InterviewRound, Mode
from .timeutil import IST

HHMM = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
MAX_ROUNDS = 6


def clean_working_hours(value) -> dict:
    if not isinstance(value, dict):
        raise ValidationError(
            {"working_hours": "Send working hours per weekday (1 = Monday ... 7 = Sunday)."}
        )
    out = {}
    for key, window in value.items():
        if str(key) not in {str(d) for d in range(1, 8)}:
            raise ValidationError({"working_hours": f"Unknown weekday {key!r}."})
        if window in (None, [], ""):
            continue
        if not (
            isinstance(window, (list, tuple)) and len(window) == 2 and all(HHMM.match(str(t)) for t in window)
        ):
            raise ValidationError({"working_hours": f'Use ["HH:MM", "HH:MM"] for weekday {key}.'})
        if window[0] >= window[1]:
            raise ValidationError({"working_hours": f"Weekday {key}: the end must be after the start."})
        out[str(key)] = [str(window[0]), str(window[1])]
    return out


def parse_moment(value, field: str) -> datetime:
    """ISO datetime; a time without an offset is read as IST."""
    moment = parse_datetime(str(value or ""))
    if moment is None:
        raise ValidationError({field: "Use a date and time like 2026-12-01T10:30."})
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=IST)
    return moment


def clean_block(payload: dict, now: datetime) -> tuple[datetime, datetime, str]:
    start = parse_moment(payload.get("starts_at"), "starts_at")
    end = parse_moment(payload.get("ends_at"), "ends_at")
    if end <= start:
        raise ValidationError({"ends_at": "The end must be after the start."})
    if end <= now:
        raise ValidationError({"ends_at": "Blocked time must be in the future."})
    if end - start > timedelta(days=31):
        raise ValidationError({"ends_at": "Block at most 31 days at a time."})
    return start, end, str(payload.get("reason") or "").strip()[:120]


def _clean_round(raw: dict, index: int) -> dict:
    errors = {}
    name = str(raw.get("name") or "").strip()[:60]
    if not name:
        errors[f"rounds.{index}.name"] = "Name the round."
    try:
        minutes = int(raw.get("duration_minutes") or 0)
    except (TypeError, ValueError):
        minutes = 0
    if minutes < 15 or minutes > 180 or minutes % 15:
        errors[f"rounds.{index}.duration_minutes"] = "Use 15 to 180 minutes, in steps of 15."
    mode = raw.get("mode") or Mode.VIDEO
    if mode not in Mode.values:
        errors[f"rounds.{index}.mode"] = "Choose video, in person or phone."
    try:
        need = int(raw.get("interviewers_needed") or 1)
    except (TypeError, ValueError):
        need = 0
    if need < 1 or need > 4:
        errors[f"rounds.{index}.interviewers_needed"] = "Use 1 to 4 interviewers."
    pool_ids = [str(p) for p in raw.get("pool") or []]
    pool = list(User.objects.filter(id__in=pool_ids, is_active=True).exclude(role=Role.CANDIDATE))
    if len(pool) != len(set(pool_ids)):
        errors[f"rounds.{index}.pool"] = "Pool members must be active staff."
    elif len(pool) < need:
        errors[f"rounds.{index}.pool"] = "The pool needs at least as many people as the round needs."
    if errors:
        raise ValidationError(errors)
    return {
        "id": raw.get("id"),
        "name": name,
        "duration_minutes": minutes,
        "mode": mode,
        "interviewers_needed": need,
        "pool": pool,
    }


@transaction.atomic
def update_plan(plan, payload: dict):
    if "hira_enabled" in payload:
        plan.hira_enabled = bool(payload["hira_enabled"])
        plan.save(update_fields=["hira_enabled", "updated_at"])
    if "rounds" not in payload:
        return plan
    raw_rounds = payload["rounds"]
    if not isinstance(raw_rounds, list) or not 1 <= len(raw_rounds) <= MAX_ROUNDS:
        raise ValidationError({"rounds": f"Plan 1 to {MAX_ROUNDS} rounds."})
    cleaned = [_clean_round(r, i) for i, r in enumerate(raw_rounds)]
    existing = {str(r.id): r for r in plan.rounds.all()}
    keep = {str(c["id"]) for c in cleaned if c["id"]}
    for round_id, round_ in existing.items():
        if round_id not in keep:
            if round_.interviews.exists():
                raise ValidationError(
                    {"rounds": f'"{round_.name}" already has interviews, so it cannot be removed.'}
                )
            round_.delete()
    # Park existing rounds on high order numbers so reordering never trips the unique constraint.
    for n, round_ in enumerate(plan.rounds.all()):
        InterviewRound.objects.filter(pk=round_.pk).update(order=100 + n)
    for order, c in enumerate(cleaned, start=1):
        round_ = existing.get(str(c["id"])) if c["id"] else None
        if round_ is None:
            round_ = InterviewRound(plan=plan)
        round_.order, round_.name, round_.duration_minutes = order, c["name"], c["duration_minutes"]
        round_.mode, round_.interviewers_needed = c["mode"], c["interviewers_needed"]
        round_.save()
        round_.pool.set(c["pool"])
    return plan

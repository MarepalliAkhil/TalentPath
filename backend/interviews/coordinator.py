"""HIRA the recruiting coordinator: rule-based, deterministic interview scheduling.

Entry points:
- on_stage_changed: called by applications.services when a candidate moves stage.
- propose / hold / confirm / reschedule: the candidate's slot picking.
- decline / mark_no_show: interviewer actions.
- schedule_manually: recruiters when "Let HIRA schedule" is off (same clash checks).
- tick: reminders, completions, expired holds, scorecard chasing (cron).
Every HIRA action is logged with hira.activity.log (also mirrored to the audit log).
"""

from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import Role, User
from applications.blind import is_blind
from applications.models import ApplicationStatus as S
from core.audit import audit
from core.brand import get_brand
from hira import activity
from hira.models import HiraAction
from notifications.services import notify

from . import claims, rules, tokens
from .ics import build_ics
from .models import (
    ACTIVE_INTERVIEW,
    POSITIVE,
    AssignmentStatus,
    Attention,
    ClaimKind,
    Interview,
    InterviewAssignment,
    InterviewerProfile,
    InterviewPlan,
    InterviewRound,
    InterviewStatus,
    Mode,
    SlotOffer,
    SlotStatus,
)
from .slots import find_slots, free_replacements
from .timeutil import fmt

# ----------------------------------------------------------------------- plans
DEFAULT_ROUNDS = [
    # name, minutes, mode, interviewers needed, pool kind
    ("Technical 1", 60, Mode.VIDEO, 1, "skills"),
    ("Technical 2", 60, Mode.VIDEO, 2, "skills"),
    ("Hiring manager", 45, Mode.VIDEO, 1, "manager"),
    ("HR", 30, Mode.PHONE, 1, "hr"),
]


def skill_pool(job) -> list:
    """Active interviewers (not the candidate side) sharing at least one required skill with the job."""
    required = list(job.required_skills.values_list("id", flat=True))
    qs = InterviewerProfile.objects.filter(active=True, user__is_active=True).exclude(
        user__role=Role.CANDIDATE
    )
    matched = qs.filter(skills__in=required).distinct() if required else qs.none()
    users = [p.user for p in matched.select_related("user")]
    if len(users) < 2:  # small teams: fall back to every active interviewer
        users = [p.user for p in qs.select_related("user")]
    return sorted(users, key=lambda u: str(u.id))


def build_default_plan(job) -> InterviewPlan:
    plan, _ = InterviewPlan.objects.get_or_create(job=job)
    if plan.rounds.exists():
        return plan
    hr = list(User.objects.filter(role=Role.HR_ADMIN, is_active=True).order_by("id"))
    skills = skill_pool(job)
    for order, (name, minutes, mode, need, kind) in enumerate(DEFAULT_ROUNDS, start=1):
        if kind == "manager":
            pool = [job.hiring_manager] if job.hiring_manager_id else skills[:1]
        elif kind == "hr":
            pool = hr
        else:
            pool = skills
        round_ = InterviewRound.objects.create(
            plan=plan,
            order=order,
            name=name,
            duration_minutes=minutes,
            mode=mode,
            interviewers_needed=max(1, min(need, len(pool) or 1)),
        )
        round_.pool.set(pool)
    return plan


def get_plan(job) -> InterviewPlan:
    plan = InterviewPlan.objects.filter(job=job).first()
    return plan if plan and plan.rounds.exists() else build_default_plan(job)


def round_outcome(interview) -> str | None:
    """'passed', 'not_passed' or None while feedback is incomplete."""
    if interview.status != InterviewStatus.COMPLETED:
        return None
    assigned = set(
        interview.assignments.filter(status=AssignmentStatus.ASSIGNED).values_list(
            "interviewer_id", flat=True
        )
    )
    cards = list(interview.scorecards.all())
    if not assigned or not assigned <= {c.interviewer_id for c in cards}:
        return None
    yes = sum(1 for c in cards if c.recommendation in POSITIVE)
    no = len(cards) - yes
    return "passed" if yes >= no and yes > 0 else "not_passed"


def round_status(application) -> list[dict]:
    plan = get_plan(application.job)
    interviews = list(application.interviews.select_related("round").order_by("created_at"))
    rows = []
    for round_ in plan.rounds.all():
        mine = [i for i in interviews if i.round_id == round_.id]
        latest = mine[-1] if mine else None
        rows.append(
            {"round": round_, "interview": latest, "outcome": round_outcome(latest) if latest else None}
        )
    return rows


def next_round(application):
    """The first round not yet passed, or None if one is in progress, failed, or all passed."""
    for row in round_status(application):
        interview, outcome = row["interview"], row["outcome"]
        if outcome == "passed":
            continue
        if interview is None or interview.status in (InterviewStatus.CANCELLED, InterviewStatus.NO_SHOW):
            return row["round"]
        return None
    return None


def final_round_passed(application) -> bool:
    rows = round_status(application)
    return bool(rows) and all(r["outcome"] == "passed" for r in rows)


# --------------------------------------------------------------- notifications
def who(application) -> str:
    """Candidate label for staff: the code while blind, else the name."""
    return application.candidate_code if is_blind(application) else application.candidate.full_name


def meeting_details(interview) -> tuple[str, str]:
    """(location, note). Links and places are simulated in this demo."""
    if interview.mode == Mode.VIDEO:
        return (
            interview.meeting_link,
            "Video call. Simulated meeting link for this demo; nobody will be there.",
        )
    if interview.mode == Mode.IN_PERSON:
        place = f"{get_brand()['employerName']} office, {interview.application.job.location.name} (simulated)"
        return place, "In person. Simulated address for this demo."
    return "Phone call", "We will call your registered number (simulated for this demo)."


def interviewers_of(interview) -> list[User]:
    return [
        a.interviewer
        for a in interview.assignments.select_related("interviewer").filter(status=AssignmentStatus.ASSIGNED)
    ]


def _ics(interview, audience: str) -> tuple:
    job = interview.application.job
    location, note = meeting_details(interview)
    if audience == "candidate":
        summary = f"Interview: {job.title} ({interview.round.name})"
    else:
        summary = f"Interview {who(interview.application)}: {job.title} ({interview.round.name})"
    description = f"{note} Scheduled by HIRA, {get_brand()['assistant']['display']}."
    text = build_ics(
        interview,
        summary=summary,
        description=description,
        location=location,
        sequence=interview.reschedule_count,
    )
    return ("interview.ics", "text/calendar", text)


def _notify_recruiter(application, *, title: str, body: str, silent: bool) -> None:
    if silent:
        return
    notify(
        application.job.created_by,
        kind="hira_needs_you",
        title=title,
        body=body,
        link=f"/recruiter/jobs/{application.job_id}/applications?open={application.id}",
    )


def _announce_slots(interview, silent: bool) -> None:
    job = interview.application.job
    link = tokens.issue(interview)
    if silent:
        return
    notify(
        interview.application.candidate,
        kind="interview_slots",
        title=f"Pick a time for your {interview.round.name} interview",
        body=(
            f"HIRA found {interview.slots.filter(status=SlotStatus.OPEN).count()} times for your "
            f"{job.title} interview. Choose one from your dashboard or the link in this email. "
            "The link works once and expires in 72 hours."
        ),
        link="/candidate",
        email_link=f"/schedule/{link}",
    )


def _announce_booking(interview, *, rescheduled: bool, silent: bool) -> None:
    if silent:
        return
    job = interview.application.job
    when = fmt(interview.starts_at)
    location, note = meeting_details(interview)
    verb = "rescheduled" if rescheduled else "confirmed"
    notify(
        interview.application.candidate,
        kind="interview_scheduled",
        title=f"Interview {verb}: {job.title}, {when}",
        body=(
            f"{interview.round.name}, {interview.round.duration_minutes} minutes. {location}. {note} A "
            "calendar invite (.ics) is attached."
        ),
        link="/candidate",
        attachment=_ics(interview, "candidate"),
    )
    for person in interviewers_of(interview):
        notify(
            person,
            kind="interview_scheduled",
            title=f"Interview {verb}: {who(interview.application)}, {when}",
            body=f"{job.title}, {interview.round.name}. Your scorecard is due 24 hours after the interview.",
            link="/interviews",
            attachment=_ics(interview, "interviewer"),
        )


# ------------------------------------------------------------------- proposing
def _start_round(application, round_, *, silent: bool) -> Interview:
    interview = Interview.objects.create(application=application, round=round_, mode=round_.mode)
    propose(interview, silent=silent)
    return interview


def on_stage_changed(application, old: str, new: str, *, actor=None, silent: bool = False) -> None:
    if new == S.INTERVIEW:
        plan = get_plan(application.job)
        if not plan.hira_enabled:
            return
        round_ = next_round(application)
        if round_ is not None and not application.interviews.filter(status__in=ACTIVE_INTERVIEW).exists():
            _start_round(application, round_, silent=silent)
    elif new in (S.OFFER, S.REJECTED, S.WITHDRAWN, S.HIRED):
        for interview in application.interviews.filter(status__in=ACTIVE_INTERVIEW):
            cancel(interview, reason=f"application_{new}")


def cancel(interview, *, reason: str) -> None:
    with transaction.atomic():
        claims.release(interview)
        interview.slots.filter(status__in=[SlotStatus.OPEN, SlotStatus.HELD]).update(
            status=SlotStatus.WITHDRAWN
        )
        interview.status = InterviewStatus.CANCELLED
        interview.attention = ""
        interview.save(update_fields=["status", "attention", "updated_at"])
    audit(None, "interviews.cancelled", target=interview, reason=reason)


def propose(interview, *, silent: bool = False, avoid_starts=(), now=None, reason: str = "") -> list:
    """Offer 3 to 5 fresh slots (or flag "no slots" for a person)."""
    now = now or timezone.now()
    application = interview.application
    found = find_slots(
        interview.round, application.candidate, now=now, avoid_starts=avoid_starts, ignore_interview=interview
    )
    with transaction.atomic():
        claims.release(interview, kind=ClaimKind.HOLD)
        interview.slots.filter(status__in=[SlotStatus.OPEN, SlotStatus.HELD]).update(
            status=SlotStatus.WITHDRAWN
        )
        SlotOffer.objects.bulk_create(
            [
                SlotOffer(
                    interview=interview,
                    starts_at=s.starts_at,
                    ends_at=s.ends_at,
                    interviewer_ids=list(s.interviewer_ids),
                )
                for s in found
            ]
        )
        before = {"attention": interview.attention}
        if not found:
            interview.attention = Attention.NO_SLOTS
        elif interview.attention == Attention.NO_SLOTS:
            interview.attention = ""
        interview.save(update_fields=["attention", "updated_at"])
    if not found:
        activity.log(
            HiraAction.NO_SLOTS,
            interview=interview,
            reason_code="no_common_free_time",
            before=before,
            after={"slots": 0},
        )
        _notify_recruiter(
            application,
            title=f"HIRA needs you: no free slots for {who(application)}",
            body=(
                f"No common free time in the next {rules.HORIZON_DAYS} days for {interview.round.name} "
                f"({application.job.title}). Add interviewers or schedule by hand."
            ),
            silent=silent,
        )
        return []
    activity.log(
        HiraAction.SLOTS_PROPOSED,
        interview=interview,
        reason_code=reason or "stage_interview",
        after={"slots": [s.starts_at.isoformat() for s in found]},
    )
    _announce_slots(interview, silent)
    return found


def _lock(interview) -> Interview:
    return (
        Interview.objects.select_for_update()
        .select_related("round", "application", "application__job", "application__candidate")
        .get(pk=interview.pk)
    )


def _check_candidate_slot(interview, slot, now) -> None:
    if interview.status != InterviewStatus.PENDING:
        raise ValidationError({"slot": "This interview is not waiting for a slot."})
    if slot.interview_id != interview.id or slot.status not in (SlotStatus.OPEN, SlotStatus.HELD):
        raise ValidationError({"slot": "That slot is no longer offered."})
    if slot.starts_at <= now + timedelta(hours=1):
        raise ValidationError({"slot": "That slot is too soon now. Please choose another."})


def _hold_locked(interview, slot, now) -> SlotOffer:
    """Hold `slot` for this interview (caller holds the transaction and the interview lock)."""
    if slot.status == SlotStatus.HELD and slot.held_until and slot.held_until > now:
        return slot  # already held for this interview
    claims.release(interview, kind=ClaimKind.HOLD)
    interview.slots.filter(status=SlotStatus.HELD).update(status=SlotStatus.OPEN, held_until=None)
    people = [*slot.interviewer_ids, str(interview.application.candidate_id)]
    until = now + timedelta(minutes=rules.HOLD_MINUTES)
    claims.book(
        people=people,
        interviewer_ids=slot.interviewer_ids,
        start=slot.starts_at,
        end=slot.ends_at,
        kind=ClaimKind.HOLD,
        interview=interview,
        slot=slot,
        expires_at=until,
        now=now,
    )
    SlotOffer.objects.filter(pk=slot.pk).update(status=SlotStatus.HELD, held_until=until)
    slot.status, slot.held_until = SlotStatus.HELD, until
    return slot


def _slot_lost(interview, slot_id, now) -> None:
    """Someone else got that time first: stop offering it, and refresh the list if it ran out."""
    SlotOffer.objects.filter(pk=slot_id, interview=interview, status=SlotStatus.OPEN).update(
        status=SlotStatus.WITHDRAWN
    )
    interview.refresh_from_db()
    if (
        interview.status == InterviewStatus.PENDING
        and not interview.slots.filter(status=SlotStatus.OPEN).exists()
    ):
        propose(interview, now=now, reason="slots_refreshed", silent=True)


def hold(interview, slot_id, *, now=None) -> SlotOffer:
    now = now or timezone.now()
    try:
        with transaction.atomic():
            interview = _lock(interview)
            slot = SlotOffer.objects.filter(pk=slot_id, interview=interview).first()
            if slot is None:
                raise ValidationError({"slot": "Choose one of the offered slots."})
            _check_candidate_slot(interview, slot, now)
            return _hold_locked(interview, slot, now)
    except claims.SlotTaken:
        _slot_lost(interview, slot_id, now)
        raise


def _meeting_link(interview) -> str:
    return f"https://meet.example/simulated/{interview.id.hex[:10]}" if interview.mode == Mode.VIDEO else ""


def _occupy(interview, start, end, interviewer_ids, *, by: str, slot=None, now=None) -> None:
    """Turn holds into interview claims and fill in the interview. Caller holds the transaction."""
    now = now or timezone.now()
    claims.release(interview)
    claims.book(
        people=[*interviewer_ids, str(interview.application.candidate_id)],
        interviewer_ids=interviewer_ids,
        start=start,
        end=end,
        kind=ClaimKind.INTERVIEW,
        interview=interview,
        slot=slot,
        now=now,
    )
    interview.assignments.filter(status=AssignmentStatus.ASSIGNED).delete()
    for user_id in interviewer_ids:
        InterviewAssignment.objects.update_or_create(
            interview=interview,
            interviewer_id=user_id,
            defaults={"status": AssignmentStatus.ASSIGNED, "decline_reason": ""},
        )
    interview.status = InterviewStatus.SCHEDULED
    interview.starts_at, interview.ends_at = start, end
    interview.mode = interview.round.mode
    interview.meeting_link = _meeting_link(interview)
    interview.scheduled_by = by
    interview.scorecard_due_at = end + rules.SCORECARD_DUE
    interview.reminder_24h_sent_at = interview.reminder_1h_sent_at = None
    interview.attention = ""
    interview.save()
    interview.slots.filter(status__in=[SlotStatus.OPEN, SlotStatus.HELD]).exclude(
        pk=getattr(slot, "pk", None)
    ).update(status=SlotStatus.WITHDRAWN)
    if slot is not None:
        SlotOffer.objects.filter(pk=slot.pk).update(status=SlotStatus.TAKEN, held_until=None)


def confirm(interview, slot_id, *, link=None, now=None, silent: bool = False) -> Interview:
    """Book the chosen slot. Holds it first if needed (holds may have expired)."""
    now = now or timezone.now()
    try:
        with transaction.atomic():
            interview = _lock(interview)
            slot = SlotOffer.objects.filter(pk=slot_id, interview=interview).first()
            if slot is None:
                raise ValidationError({"slot": "Choose one of the offered slots."})
            _check_candidate_slot(interview, slot, now)
            slot = _hold_locked(interview, slot, now)
            rescheduled = interview.reschedule_count > 0
            before = {"status": interview.status, "attention": interview.attention}
            _occupy(
                interview, slot.starts_at, slot.ends_at, slot.interviewer_ids, by="hira", slot=slot, now=now
            )
            if link is not None:
                tokens.use(link, now)
    except claims.SlotTaken:
        _slot_lost(interview, slot_id, now)
        raise
    activity.log(
        HiraAction.INTERVIEW_SCHEDULED,
        interview=interview,
        reason_code="rescheduled" if rescheduled else "candidate_picked",
        before=before,
        after={"starts_at": interview.starts_at.isoformat(), "interviewers": len(slot.interviewer_ids)},
    )
    _announce_booking(interview, rescheduled=rescheduled, silent=silent)
    return interview


def reschedule(interview, *, now=None, silent: bool = False) -> list:
    """Candidate asks for another time: up to 2 times, until 12 hours before."""
    now = now or timezone.now()
    with transaction.atomic():
        interview = _lock(interview)
        if interview.status != InterviewStatus.SCHEDULED:
            raise ValidationError({"interview": "Only a scheduled interview can be rescheduled."})
        if interview.starts_at - now < rules.RESCHEDULE_CUTOFF:
            raise ValidationError(
                {"interview": "Interviews can be rescheduled until 12 hours before they start."}
            )
        if interview.reschedule_count >= rules.RESCHEDULE_LIMIT:
            limit_hit = interview.attention != Attention.RESCHEDULE_LIMIT
            Interview.objects.filter(pk=interview.pk).update(attention=Attention.RESCHEDULE_LIMIT)
        else:
            limit_hit = None
    if limit_hit is not None:
        if limit_hit:
            activity.log(
                HiraAction.RESCHEDULE_LIMIT,
                interview=interview,
                reason_code="limit_reached",
                after={"count": interview.reschedule_count},
            )
            _notify_recruiter(
                interview.application,
                title=f"HIRA needs you: {who(interview.application)} asked to reschedule again",
                body=(
                    f"The candidate has used both reschedules for {interview.round.name}. Reschedule by hand "
                    "if you can."
                ),
                silent=silent,
            )
        raise ValidationError(
            {"interview": "You have already rescheduled twice. We have asked the recruiter to help you."}
        )
    old_start = interview.starts_at
    previous = interviewers_of(interview)
    with transaction.atomic():
        interview = _lock(interview)
        claims.release(interview)
        interview.assignments.filter(status=AssignmentStatus.ASSIGNED).delete()
        interview.status = InterviewStatus.PENDING
        interview.reschedule_count += 1
        interview.starts_at = interview.ends_at = None
        interview.meeting_link = ""
        interview.save()
    activity.log(
        HiraAction.RESCHEDULE_HANDLED,
        interview=interview,
        reason_code="candidate_request",
        before={"starts_at": old_start.isoformat()},
        after={"reschedule_count": interview.reschedule_count},
    )
    if not silent:
        for person in previous:
            notify(
                person,
                kind="interview_moved",
                title=f"Interview moved: {who(interview.application)}, was {fmt(old_start)}",
                body=(
                    "The candidate asked for another time. HIRA is offering new slots; you will get a new "
                    "invite if you are picked."
                ),
                link="/interviews",
            )
    return propose(interview, silent=silent, avoid_starts=[old_start], now=now, reason="reschedule")


def decline(interview, interviewer, *, reason: str = "", now=None, silent: bool = False) -> dict:
    """An interviewer cannot make it: find a free replacement from the same pool, else offer new slots."""
    now = now or timezone.now()
    reason = (reason or "").strip()[:200]
    with transaction.atomic():
        interview = _lock(interview)
        assignment = interview.assignments.filter(
            interviewer=interviewer, status=AssignmentStatus.ASSIGNED
        ).first()
        if assignment is None or interview.status != InterviewStatus.SCHEDULED:
            raise ValidationError({"interview": "You are not on this scheduled interview."})
        if interview.starts_at <= now:
            raise ValidationError({"interview": "This interview has already started."})
        assignment.status, assignment.decline_reason = AssignmentStatus.DECLINED, reason
        assignment.save(update_fields=["status", "decline_reason"])
        claims.release(interview, person_ids=[interviewer.id])
        current = [str(a.interviewer_id) for a in interview.assignments.all()]
        options = free_replacements(
            interview.round, interview.starts_at, interview.ends_at, exclude_users=current
        )
        replacement = None
        for option in options:
            try:
                with transaction.atomic():
                    claims.book(
                        people=[option],
                        interviewer_ids=[option],
                        start=interview.starts_at,
                        end=interview.ends_at,
                        kind=ClaimKind.INTERVIEW,
                        interview=interview,
                        now=now,
                    )
            except claims.SlotTaken:
                continue
            replacement = User.objects.get(pk=option)
            InterviewAssignment.objects.create(interview=interview, interviewer=replacement)
            break
    audit(None, "interviews.declined", actor=interviewer, target=interview)
    if replacement is not None:
        activity.log(
            HiraAction.INTERVIEWER_REPLACED,
            interview=interview,
            reason_code="interviewer_declined",
            before={"declined": 1},
            after={"replacement_found": True},
        )
        if not silent:
            notify(
                replacement,
                kind="interview_scheduled",
                title=f"New interview for you: {who(interview.application)}, {fmt(interview.starts_at)}",
                body=(
                    f"HIRA added you as a replacement interviewer for {interview.application.job.title} "
                    f"({interview.round.name})."
                ),
                link="/interviews",
                attachment=_ics(interview, "interviewer"),
            )
        return {"replaced": True, "replacement": replacement.full_name}
    # Nobody free at that time: move the interview back to picking and offer new slots.
    old_start = interview.starts_at
    with transaction.atomic():
        interview = _lock(interview)
        claims.release(interview)
        interview.assignments.filter(status=AssignmentStatus.ASSIGNED).delete()
        interview.status = InterviewStatus.PENDING
        interview.starts_at = interview.ends_at = None
        interview.meeting_link = ""
        interview.attention = Attention.REPLACEMENT_FAILED
        interview.save()
    activity.log(
        HiraAction.REPLACEMENT_FAILED,
        interview=interview,
        reason_code="no_free_interviewer",
        before={"starts_at": old_start.isoformat()},
    )
    _notify_recruiter(
        interview.application,
        title=f"HIRA needs you: no replacement interviewer for {who(interview.application)}",
        body=(
            f"An interviewer declined {interview.round.name} and nobody in the pool was free. HIRA has "
            "offered the candidate new times."
        ),
        silent=silent,
    )
    if not silent:
        notify(
            interview.application.candidate,
            kind="interview_slots",
            title=f"We need to move your {interview.application.job.title} interview",
            body=(
                "Sorry, an interviewer can no longer make that time. Please pick a new slot. This does not "
                "count as one of your reschedules."
            ),
            link="/candidate",
        )
    # The "replacement failed" flag stays until the candidate books a new slot.
    propose(interview, silent=silent, avoid_starts=[old_start], now=now, reason="interviewer_declined")
    return {"replaced": False}


def mark_no_show(interview, interviewer, *, now=None) -> Interview:
    now = now or timezone.now()
    with transaction.atomic():
        interview = _lock(interview)
        if not interview.assignments.filter(
            interviewer=interviewer, status=AssignmentStatus.ASSIGNED
        ).exists():
            raise ValidationError({"interview": "You are not on this interview."})
        if (
            interview.status not in (InterviewStatus.SCHEDULED, InterviewStatus.COMPLETED)
            or interview.starts_at > now
        ):
            raise ValidationError({"interview": "You can mark a no-show once the interview has started."})
        if interview.scorecards.exists():
            raise ValidationError({"interview": "Feedback was already submitted for this interview."})
        interview.status = InterviewStatus.NO_SHOW
        interview.save(update_fields=["status", "updated_at"])
    audit(None, "interviews.no_show", actor=interviewer, target=interview)
    notify(
        interview.application.job.created_by,
        kind="interview_no_show",
        title=f"No-show: {who(interview.application)} for {interview.round.name}",
        body=(
            f"{interviewer.full_name} marked the candidate as not joining. Decide whether to offer a new "
            "time."
        ),
        link=f"/recruiter/jobs/{interview.application.job_id}/applications?open={interview.application_id}",
    )
    return interview


def schedule_manually(application, round_, start: datetime, interviewer_ids, actor, *, now=None) -> Interview:
    """Recruiter schedules by hand. Same clash checks (claims, blocked time) as HIRA."""
    now = now or timezone.now()
    interviewer_ids = sorted({str(i) for i in interviewer_ids})
    if not interviewer_ids:
        raise ValidationError({"interviewer_ids": "Choose at least one interviewer."})
    staff = User.objects.filter(id__in=interviewer_ids, is_active=True).exclude(role=Role.CANDIDATE)
    if staff.count() != len(interviewer_ids):
        raise ValidationError({"interviewer_ids": "Interviewers must be active staff."})
    if start <= now:
        raise ValidationError({"starts_at": "Choose a time in the future."})
    end = start + timedelta(minutes=round_.duration_minutes)
    with transaction.atomic():
        interview = (
            Interview.objects.select_for_update()
            .filter(application=application, round=round_, status__in=ACTIVE_INTERVIEW)
            .first()
        )
        rescheduled = interview is not None and interview.status == InterviewStatus.SCHEDULED
        if interview is None:
            interview = Interview.objects.create(application=application, round=round_, mode=round_.mode)
        interview = _lock(interview)
        before = {"status": interview.status, "attention": interview.attention}
        _occupy(interview, start, end, interviewer_ids, by="manual", now=now)
    activity.log(
        HiraAction.MANUAL_SCHEDULED,
        interview=interview,
        reason_code="recruiter_scheduled",
        before=before,
        after={"starts_at": start.isoformat(), "interviewers": len(interviewer_ids)},
    )
    audit(None, "interviews.manual_schedule", actor=actor, target=interview)
    _announce_booking(interview, rescheduled=rescheduled, silent=False)
    return interview


def after_scorecard(interview, *, silent: bool = False) -> None:
    """When a round's feedback is complete: start the next round, or tell the recruiter."""
    outcome = round_outcome(interview)
    if outcome is None:
        return
    application = interview.application
    if outcome == "not_passed":
        _notify_recruiter(
            application,
            title=f"Feedback complete for {who(application)}: not recommended",
            body=f"{interview.round.name} feedback leans no. Review the scorecards and decide next steps.",
            silent=silent,
        )
        return
    round_ = next_round(application)
    plan = get_plan(application.job)
    if round_ is None:
        _notify_recruiter(
            application,
            title=f"{who(application)} passed the final round",
            body=(
                f"All interview rounds for {application.job.title} are complete and positive. You can draft "
                "an offer."
            ),
            silent=silent,
        )
        return
    if plan.hira_enabled and application.status == S.INTERVIEW:
        new = _start_round(application, round_, silent=silent)
        activity.log(
            HiraAction.NEXT_ROUND,
            interview=new,
            reason_code="previous_round_passed",
            after={"round": round_.name},
        )


# ------------------------------------------------------------------------ cron
def complete_finished(now) -> int:
    done = Interview.objects.filter(status=InterviewStatus.SCHEDULED, ends_at__lte=now)
    return done.update(status=InterviewStatus.COMPLETED, completed_at=now)


def expire_holds(now) -> int:
    interview_ids = claims.release_expired_holds(now)
    for interview in Interview.objects.filter(id__in=interview_ids, status=InterviewStatus.PENDING):
        activity.log(HiraAction.HOLD_EXPIRED, interview=interview, reason_code="hold_timeout", at=now)
    return len(interview_ids)


def send_reminders(now) -> int:
    """24 hours and 1 hour before, to the candidate and the interviewers. Each sent once."""
    sent = 0
    for label, delta in rules.REMINDERS:
        field = f"reminder_{label}_sent_at"
        due = Interview.objects.filter(
            status=InterviewStatus.SCHEDULED,
            starts_at__gt=now,
            starts_at__lte=now + delta,
            **{f"{field}__isnull": True},
        )
        if label == "24h":
            # Only a "day before" reminder: skip it for bookings made at short notice.
            due = due.filter(starts_at__gt=now + rules.DAY_REMINDER_LATEST)
        for interview in due.select_related(
            "application", "application__job", "application__candidate", "round"
        ):
            if not Interview.objects.filter(pk=interview.pk, **{f"{field}__isnull": True}).update(
                **{field: now}
            ):
                continue  # another tick got there first
            when = fmt(interview.starts_at)
            location, _ = meeting_details(interview)
            job = interview.application.job
            notify(
                interview.application.candidate,
                kind="interview_reminder",
                title=f"Reminder: {job.title} interview {'on ' + when if label == '24h' else 'in 1 hour'}",
                body=f"{interview.round.name} at {when}. {location}.",
                link="/candidate",
            )
            for person in interviewers_of(interview):
                notify(
                    person,
                    kind="interview_reminder",
                    title=f"Reminder: interview with {who(interview.application)} at {when}",
                    body=f"{job.title}, {interview.round.name}. {location}.",
                    link="/interviews",
                )
            activity.log(HiraAction.REMINDER_SENT, interview=interview, reason_code=label, at=now)
            sent += 1
    return sent


def chase_scorecards(now) -> dict:
    """Chase missing scorecards once they are overdue (every 24 hours); flag for a person after 48 hours."""
    chased = flagged = 0
    overdue = InterviewAssignment.objects.filter(
        status=AssignmentStatus.ASSIGNED,
        interview__status=InterviewStatus.COMPLETED,
        interview__scorecard_due_at__lte=now,
    ).select_related(
        "interview",
        "interview__application",
        "interview__application__job",
        "interview__round",
        "interviewer",
    )
    for assignment in overdue:
        interview = assignment.interview
        if interview.scorecards.filter(interviewer_id=assignment.interviewer_id).exists():
            continue
        if assignment.chased_at is None or assignment.chased_at <= now - rules.CHASE_EVERY:
            InterviewAssignment.objects.filter(pk=assignment.pk).update(chased_at=now)
            notify(
                assignment.interviewer,
                kind="scorecard_due",
                title=f"Scorecard overdue: {who(interview.application)}",
                body=(
                    f"Please submit your feedback for {interview.application.job.title} "
                    f"({interview.round.name}). It was due {fmt(interview.scorecard_due_at)}."
                ),
                link=f"/interviews/{interview.id}/scorecard",
            )
            activity.log(
                HiraAction.SCORECARD_CHASED,
                interview=interview,
                subject_user=assignment.interviewer,
                reason_code="overdue",
                at=now,
            )
            chased += 1
        if assignment.overdue_flagged_at is None and interview.ends_at <= now - rules.OVERDUE_NEEDS_YOU:
            InterviewAssignment.objects.filter(pk=assignment.pk).update(overdue_flagged_at=now)
            activity.log(
                HiraAction.SCORECARD_OVERDUE,
                interview=interview,
                subject_user=assignment.interviewer,
                reason_code="overdue_48h",
                at=now,
            )
            flagged += 1
    return {"chased": chased, "flagged": flagged}


def tick(now=None) -> dict:
    now = now or timezone.now()
    return {
        "holds_released": expire_holds(now),
        "interviews_completed": complete_finished(now),
        "reminders_sent": send_reminders(now),
        **{f"scorecards_{k}": v for k, v in chase_scorecards(now).items()},
    }


def candidate_interviews(user):
    return (
        Interview.objects.filter(application__candidate=user)
        .exclude(status=InterviewStatus.CANCELLED)
        .select_related("round", "application", "application__job")
        .order_by("created_at")
    )


def staff_can_see(user, interview) -> bool:
    job = interview.application.job
    if user.role == Role.HR_ADMIN:
        return True
    if user.role == Role.RECRUITER and job.created_by_id == user.id:
        return True
    if user.role == Role.HIRING_MANAGER and job.hiring_manager_id == user.id:
        return True
    return interview.assignments.filter(interviewer=user).exists()


def assigned_interviews(user):
    return (
        Interview.objects.filter(assignments__interviewer=user, assignments__status=AssignmentStatus.ASSIGNED)
        .filter(Q(status__in=[InterviewStatus.SCHEDULED, InterviewStatus.COMPLETED, InterviewStatus.NO_SHOW]))
        .select_related("round", "application", "application__job", "application__candidate")
        .distinct()
        .order_by("starts_at")
    )

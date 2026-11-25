"""Week 3A demo data: interviewers, interview plans, interviews in the past and
future, scorecards (submitted and overdue), offers in every state and HIRA
activity history. Everything goes through the real services where it can, so
the demo shows what the product would really do."""

import random
from datetime import datetime, time, timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import Role, User
from applications.models import Application
from applications.models import ApplicationStatus as S
from hira import activity
from hira.models import HiraAction, HiraActivity
from interviews import claims, coordinator, scorecards
from interviews.models import (
    Attention,
    BlockedTime,
    Interview,
    InterviewAssignment,
    InterviewerProfile,
    InterviewStatus,
    Scorecard,
    SlotStatus,
)
from interviews.timeutil import IST, today_ist
from jobs.models import Job
from offers import services as offers
from offers.models import Offer
from org.models import Skill
from seeding import demo_data as D

HISTORY_CODE = "seed_history"
COMMENTS = {
    1: "Could not show this in the exercise, even with hints.",
    2: "Partial answers; needed a lot of guidance.",
    5: "Exceptional: clear, structured and well reasoned.",
}
SUMMARIES = [
    "Strong fundamentals and clear communication. Would enjoy working with them.",
    "Good problem solving; a little rusty on testing practice.",
    "Thoughtful answers and good questions about the team.",
]


def seed_interviewers(staff: dict) -> int:
    """Interviewer profiles with skills from the departments they cover, and weekly hours."""
    by_department: dict[str, set] = {}
    for spec in D.JOBS:
        by_department.setdefault(spec[1], set()).update(spec[5])
        by_department[spec[1]].update(spec[6])
    for key, (departments, hours) in D.INTERVIEWERS.items():
        user = staff[key]
        profile, created = InterviewerProfile.objects.get_or_create(
            user=user, defaults={"working_hours": hours}
        )
        if created:
            names = set().union(*[by_department.get(d, set()) for d in departments]) if departments else set()
            profile.skills.set(Skill.objects.filter(name__in=names))
    # One interviewer is on leave for two days next week (blocked time).
    arjun = staff["int_arjun"]
    if not BlockedTime.objects.filter(user=arjun).exists():
        start = datetime.combine(today_ist(timezone.now()) + timedelta(days=8), time(0, 0), tzinfo=IST)
        BlockedTime.objects.create(
            user=arjun, starts_at=start, ends_at=start + timedelta(days=2), reason="Annual leave"
        )
    return InterviewerProfile.objects.count()


def seed_plans() -> int:
    for job in Job.objects.filter(created_by__email__endswith=".example"):
        coordinator.get_plan(job)
    return Job.objects.count()


def _past_start(days_ago: int, hour: int) -> datetime:
    day = today_ist(timezone.now()) - timedelta(days=days_ago)
    return datetime.combine(day, time(hour, 0), tzinfo=IST)


def _pick(pool: list, need: int, offset: int) -> list:
    pool = sorted(pool, key=lambda u: str(u.id))
    if not pool:
        return []
    return [pool[(offset + i) % len(pool)] for i in range(min(need, len(pool)))]


def past_round(
    application, round_, *, days_ago, hour, people=None, recommendation="yes", missing=0, offset=0
):
    """A finished interview with scorecards (the last `missing` interviewers have not submitted)."""
    people = people or _pick(list(round_.pool.all()), round_.interviewers_needed, offset)
    if not people:
        return None
    start = _past_start(days_ago, hour)
    end = start + timedelta(minutes=round_.duration_minutes)
    interview = Interview.objects.create(
        application=application,
        round=round_,
        status=InterviewStatus.COMPLETED,
        starts_at=start,
        ends_at=end,
        mode=round_.mode,
        meeting_link=f"https://meet.example/simulated/{application.id.hex[:6]}{round_.order}",
        scheduled_by="hira",
        scorecard_due_at=end + timedelta(hours=24),
        completed_at=end,
        reminder_24h_sent_at=start - timedelta(hours=24),
        reminder_1h_sent_at=start - timedelta(hours=1),
    )
    for person in people:
        InterviewAssignment.objects.create(interview=interview, interviewer=person)
    rng = random.Random(str(interview.application_id) + round_.name)
    criteria = scorecards.template(application.job)
    for n, person in enumerate(people[: len(people) - missing]):
        ratings = {
            c["key"]: rng.choice([3, 4, 4, 5])
            if recommendation in ("yes", "strong_yes")
            else rng.choice([2, 3])
            for c in criteria
        }
        comments = {k: COMMENTS[v] for k, v in ratings.items() if v in COMMENTS}
        scorecards.submit(
            interview,
            person,
            ratings=ratings,
            comments=comments,
            recommendation=recommendation
            if n == 0
            else ("strong_yes" if recommendation == "yes" and n % 2 else recommendation),
            summary=SUMMARIES[n % len(SUMMARIES)],
        )
    return interview


def _cancel_pending(application):
    for interview in application.interviews.filter(
        status__in=[InterviewStatus.PENDING, InterviewStatus.SCHEDULED]
    ):
        coordinator.cancel(interview, reason="seed_history")


def _book_first(interview):
    """Book the earliest offered slot that is still free (HIRA refreshes slots when one is taken)."""
    for _ in range(8):
        interview.refresh_from_db()
        if interview.status != InterviewStatus.PENDING:
            return interview
        slot = interview.slots.filter(status=SlotStatus.OPEN).order_by("starts_at").first()
        if slot is None:
            return None
        try:
            return coordinator.confirm(interview, slot.id, silent=True)
        except claims.SlotTaken:
            continue
    return None


def pass_all_rounds(application, *, start_days_ago=12):
    _cancel_pending(application)
    plan = coordinator.get_plan(application.job)
    for n, round_ in enumerate(plan.rounds.all()):
        past_round(application, round_, days_ago=start_days_ago - 2 * n, hour=11 + n, offset=n)


def seed_interviews(staff: dict) -> dict:
    """Interview-stage applications in a spread of situations (idempotent)."""
    demo_candidate = User.objects.filter(email=f"candidate@{D.DEMO_DOMAIN}").first()
    if Scorecard.objects.filter(interview__application__candidate__email__endswith=".example").exists():
        return {"skipped": True}
    counts = {
        "pending": 0,
        "scheduled": 0,
        "past": 0,
        "overdue": 0,
        "reschedule_limit": 0,
        "no_slots": 0,
        "replaced": 0,
    }
    employee = staff["employee"]
    apps = list(
        Application.objects.filter(status=S.INTERVIEW, candidate__email__endswith=D.CANDIDATE_DOMAIN)
        .select_related("job", "candidate")
        .order_by("created_at", "id")
    )
    walkthrough_card = False
    for k, application in enumerate(apps):
        scenario = k % 6
        pending = application.interviews.filter(status=InterviewStatus.PENDING).first()
        if scenario == 0 or pending is None:
            counts["pending"] += 1
        elif scenario == 1:
            if _book_first(pending):
                counts["scheduled"] += 1
                if k % 12 == 1:  # an interviewer declines; HIRA finds a replacement
                    pending.refresh_from_db()
                    first = pending.assignments.filter(status="assigned").first()
                    if first:
                        result = coordinator.decline(
                            pending, first.interviewer, reason="Customer call moved", silent=True
                        )
                        counts["replaced"] += int(result["replaced"])
        elif scenario == 2:
            _cancel_pending(application)
            round_ = coordinator.get_plan(application.job).rounds.first()
            done = past_round(application, round_, days_ago=4, hour=12, offset=k)
            if done:
                coordinator.after_scorecard(done, silent=True)
                nxt = application.interviews.filter(status=InterviewStatus.PENDING).first()
                if nxt and _book_first(nxt):
                    counts["scheduled"] += 1
                counts["past"] += 1
        elif scenario == 3:
            _cancel_pending(application)
            round_ = coordinator.get_plan(application.job).rounds.first()
            in_pool = round_.pool.filter(pk=employee.pk).exists()
            if not walkthrough_card and in_pool:
                # For the walkthrough: Divya interviewed yesterday and still owes her scorecard.
                people = [employee]
                past_round(application, round_, days_ago=1, hour=11, people=people, missing=1)
                walkthrough_card = True
            else:
                past_round(application, round_, days_ago=4, hour=15, missing=1, offset=k)
                counts["overdue"] += 1
        elif scenario == 4:
            # Candidates who rescheduled; every other one has used both reschedules and asked again.
            limit = k % 12 == 4
            booked = _book_first(pending)
            for _ in range(2 if limit else 1):
                if booked is None:
                    break
                coordinator.reschedule(pending, silent=True)
                booked = _book_first(pending)
            if booked is not None and limit:
                try:
                    coordinator.reschedule(pending, silent=True)
                except ValidationError:
                    counts["reschedule_limit"] += 1
            counts["scheduled"] += int(booked is not None)

        elif scenario == 5:
            before = {"attention": pending.attention}
            Interview.objects.filter(pk=pending.pk).update(attention=Attention.NO_SLOTS)
            pending.slots.filter(status=SlotStatus.OPEN).update(status=SlotStatus.WITHDRAWN)
            activity.log(
                HiraAction.NO_SLOTS,
                interview=pending,
                reason_code="no_common_free_time",
                before=before,
                after={"slots": 0},
            )
            counts["no_slots"] += 1
    if not walkthrough_card:
        # Fall back to any Engineering interview so the walkthrough always has a card to fill.
        app = next((a for a in apps if a.job.department.name == "Engineering"), None)
        if app:
            _cancel_pending(app)
            past_round(
                app,
                coordinator.get_plan(app.job).rounds.first(),
                days_ago=1,
                hour=11,
                people=[employee],
                missing=1,
            )
    # The demo candidate: passed every round on their Interview-stage job (ready for an offer).
    if demo_candidate:
        for application in demo_candidate.applications.filter(status=S.INTERVIEW):
            pass_all_rounds(application)
    # Chase and flag overdue scorecards now, as the cron job would.
    counts.update({f"scorecards_{k}": v for k, v in coordinator.chase_scorecards(timezone.now()).items()})
    return counts


def _terms(application, rng, *, today):
    base = D.LEVEL_PAY.get(application.job.level.name, 1200000)
    fixed = base + rng.choice([0, 50000, 100000, 150000])
    return {
        "designation": application.job.title.split(" (")[0],
        "joining_date": (today + timedelta(days=rng.randint(30, 60))).isoformat(),
        "expires_on": (today + timedelta(days=rng.randint(7, 14))).isoformat(),
        "fixed_pay": fixed,
        "variable_pay": int(fixed * 0.1) // 1000 * 1000,
        "joining_bonus": rng.choice([0, 0, 50000, 100000]),
    }


OFFER_STATES = [
    "accepted",
    "sent",
    "pending_hm",
    "draft",
    "pending_hr",
    "approved",
    "declined",
    "expired",
    "rejected",
    "revoked",
]


def seed_offers(staff: dict) -> dict:
    """Offers in every state, on Offer-stage applications whose rounds all passed (idempotent)."""
    if Offer.objects.filter(application__candidate__email__endswith=D.CANDIDATE_DOMAIN).exists():
        return {"skipped": True}
    admin = staff["hr"]
    today = today_ist(timezone.now())
    apps = list(
        Application.objects.filter(status=S.OFFER, candidate__email__endswith=D.CANDIDATE_DOMAIN)
        .select_related("job", "job__level", "job__hiring_manager", "candidate")
        .order_by("created_at", "id")
    )
    if len(apps) < len(OFFER_STATES):
        # Top up from candidates at Interview so every state is shown.
        extra = (
            Application.objects.filter(status=S.INTERVIEW, candidate__email__endswith=D.CANDIDATE_DOMAIN)
            .exclude(interviews__scorecards__isnull=False)
            .select_related("job", "job__level", "job__hiring_manager", "candidate")
            .order_by("-created_at", "id")
            .distinct()
        )
        apps += list(extra[: len(OFFER_STATES) - len(apps)])
    made = {}
    for k, application in enumerate(apps):
        state = OFFER_STATES[k % len(OFFER_STATES)]
        if k >= len(OFFER_STATES) and state in ("rejected", "revoked", "expired", "declined"):
            continue  # one of each unhappy path is enough
        pass_all_rounds(application)
        rng = random.Random(f"offer-{application.id}")
        recruiter, manager = application.job.created_by, application.job.hiring_manager
        offer = offers.create_draft(application, recruiter, _terms(application, rng, today=today))
        if state != "draft":
            offers.submit(offer, recruiter)
        if (
            state in ("pending_hr", "approved", "sent", "accepted", "declined", "expired", "revoked")
            and manager
        ):
            offers.approve(offer, manager)
        if state == "rejected":
            offers.reject(
                offer, manager or admin, "Fixed pay is above the band for this level; please revisit."
            )
        if state in ("approved", "sent", "accepted", "declined", "expired", "revoked"):
            offers.approve(offer, admin)
        if state in ("sent", "accepted", "declined", "expired", "revoked"):
            offers.send(offer, recruiter)
        if state == "accepted":
            offers.accept(offer, application.candidate, application.candidate.full_name)
        elif state == "declined":
            offers.decline(offer, application.candidate, "I have accepted another offer closer to home.")
        elif state == "expired":
            Offer.objects.filter(pk=offer.pk).update(expires_on=today - timedelta(days=1))
            offers.expire_offers(timezone.now())
        elif state == "revoked":
            offers.revoke(offer, recruiter, "The role was put on hold after a budget review.")
        made[state] = made.get(state, 0) + 1
    return made


HISTORY_ACTIONS = [
    (HiraAction.SLOTS_PROPOSED, (1, 4)),
    (HiraAction.INTERVIEW_SCHEDULED, (0, 3)),
    (HiraAction.REMINDER_SENT, (0, 4)),
    (HiraAction.RESCHEDULE_HANDLED, (0, 1)),
    (HiraAction.SCORECARD_CHASED, (0, 1)),
    (HiraAction.INTERVIEWER_REPLACED, (0, 1)),
    (HiraAction.HOLD_EXPIRED, (0, 1)),
]


def seed_hira_history(days: int = 14) -> int:
    """Backdated activity so the briefing and the charts have something to show (idempotent)."""
    if HiraActivity.objects.filter(reason_code=HISTORY_CODE).exists():
        return 0
    now = timezone.now()
    created = 0
    recruiters = User.objects.filter(role=Role.RECRUITER, email__endswith=D.DEMO_DOMAIN).order_by("email")
    for recruiter in recruiters:
        interviews = list(
            Interview.objects.filter(application__job__created_by=recruiter)
            .exclude(status=InterviewStatus.CANCELLED)
            .select_related("application", "application__job")
            .order_by("created_at", "id")
        )
        if not interviews:
            continue
        rng = random.Random(f"history-{recruiter.email}")
        for day in range(days, 0, -1):
            for action, (low, high) in HISTORY_ACTIONS:
                for _ in range(rng.randint(low, high)):
                    interview = rng.choice(interviews)
                    at = now - timedelta(days=day, hours=rng.randint(0, 9), minutes=rng.randint(0, 59))
                    activity.log(action, interview=interview, reason_code=HISTORY_CODE, at=at)
                    created += 1
    return created


def reset_hiring(demo_users, demo_jobs) -> None:
    HiraActivity.objects.filter(
        Q(job__in=demo_jobs) | Q(application__candidate__in=demo_users) | Q(subject_user__in=demo_users)
    ).delete()

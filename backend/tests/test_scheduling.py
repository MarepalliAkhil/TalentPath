"""HIRA scheduling: slot finding, holds, booking, clashes, reminders, reschedules,
interviewer declines and no-shows. Times are pinned to a fixed Monday so the
rules (24 hours ahead, working hours, load balancing) can be checked exactly."""

import threading
from datetime import datetime, timedelta

import pytest
from django.db import IntegrityError, connection, transaction
from rest_framework.exceptions import ValidationError

from accounts.models import Role
from core.models import AuditLog
from hira.models import HiraActivity
from interviews import claims, coordinator, rules
from interviews.models import (
    AssignmentStatus,
    Attention,
    BlockedTime,
    ClaimKind,
    Interview,
    InterviewAssignment,
    InterviewPlan,
    InterviewStatus,
    SlotOffer,
    SlotStatus,
    TimeClaim,
)
from interviews.slots import find_slots
from interviews.timeutil import IST
from notifications.models import EmailOutbox, Notification

MONDAY = datetime(2030, 1, 7, 8, 0, tzinfo=IST)  # Monday 08:00 IST
postgres_only = pytest.mark.skipif(connection.vendor != "postgresql", reason="needs PostgreSQL")


@pytest.fixture
def application(plan_job, users, apply_as):
    """The candidate's application to the job with the two-round plan."""
    return apply_as(users["candidate"], plan_job)


def first_round(job):
    return InterviewPlan.objects.get(job=job).rounds.get(order=1)


def panel_round(job):
    return InterviewPlan.objects.get(job=job).rounds.get(order=2)


def new_interview(application, round_):
    return Interview.objects.create(application=application, round=round_, mode=round_.mode)


def book_busy(person, start, minutes=60, application=None, round_=None, status=InterviewStatus.SCHEDULED):
    """A scheduled interview that keeps `person` busy (and counts toward their weekly load)."""
    interview = Interview.objects.create(
        application=application,
        round=round_,
        status=status,
        starts_at=start,
        ends_at=start + timedelta(minutes=minutes),
    )
    InterviewAssignment.objects.create(interview=interview, interviewer=person)
    TimeClaim.objects.create(
        person=person,
        interview=interview,
        kind=ClaimKind.INTERVIEW,
        starts_at=start,
        ends_at=interview.ends_at,
    )
    return interview


# ------------------------------------------------------------------ slot finding
@pytest.mark.django_db
def test_slots_are_24h_ahead_inside_working_hours_and_spread(plan_job, application):
    slots = find_slots(first_round(plan_job), application.candidate, now=MONDAY)
    assert rules.MIN_SLOTS <= len(slots) <= rules.MAX_SLOTS
    for slot in slots:
        local = slot.starts_at.astimezone(IST)
        assert slot.starts_at >= MONDAY + rules.MIN_LEAD
        assert local.isoweekday() <= 5  # default hours: Monday to Friday
        assert local.hour >= 10 and slot.ends_at.astimezone(IST).hour <= 18
        assert local.minute in (0, 30)
    per_day = {}
    for slot in slots:
        per_day.setdefault(slot.starts_at.astimezone(IST).date(), []).append(slot)
    assert max(len(v) for v in per_day.values()) <= rules.MAX_SLOTS_PER_DAY
    assert [s.starts_at.astimezone(IST).strftime("%a %H:%M") for s in slots[:2]] == ["Tue 10:00", "Tue 12:00"]


@pytest.mark.django_db
def test_panel_slots_need_common_free_time(plan_job, application, interviewers):
    a, b, c, d = interviewers
    round_ = panel_round(plan_job)
    round_.pool.set([a, b])  # exactly the two people the panel needs
    # A is away all of Tuesday; B all of Wednesday.
    BlockedTime.objects.create(
        user=a,
        starts_at=datetime(2030, 1, 8, 0, 0, tzinfo=IST),
        ends_at=datetime(2030, 1, 9, 0, 0, tzinfo=IST),
    )
    BlockedTime.objects.create(
        user=b,
        starts_at=datetime(2030, 1, 9, 0, 0, tzinfo=IST),
        ends_at=datetime(2030, 1, 10, 0, 0, tzinfo=IST),
    )
    slots = find_slots(round_, application.candidate, now=MONDAY)
    assert slots
    days = {s.starts_at.astimezone(IST).day for s in slots}
    assert not days & {8, 9}  # no slot on a day when either is away
    assert all(set(s.interviewer_ids) == {str(a.id), str(b.id)} for s in slots)


@pytest.mark.django_db
def test_working_hours_per_weekday_are_respected(plan_job, application, interviewers):
    round_ = first_round(plan_job)
    for person in interviewers:
        profile = person.interviewer_profile
        profile.working_hours = {"3": ["14:00", "16:00"]}  # Wednesdays 14:00-16:00 only
        profile.save()
    slots = find_slots(round_, application.candidate, now=MONDAY)
    assert slots
    for slot in slots:
        local = slot.starts_at.astimezone(IST)
        assert local.isoweekday() == 3 and local.hour in (14, 15) and slot.ends_at.astimezone(IST).hour <= 16


@pytest.mark.django_db
def test_load_balancing_prefers_the_least_busy_interviewer_that_week(
    plan_job, application, interviewers, make_user, apply_as
):
    round_ = first_round(plan_job)
    busy_until = datetime(2030, 1, 8, 9, 0, tzinfo=IST)  # same week, before working hours
    # Interviewers 0, 1 and 2 already have interviews that week; 3 has none.
    for k, person in enumerate(interviewers[:3]):
        other = apply_as(make_user(Role.CANDIDATE), plan_job)
        book_busy(person, busy_until - timedelta(hours=k + 1), application=other, round_=round_)
    slots = find_slots(round_, application.candidate, now=MONDAY)
    assert slots[0].interviewer_ids == (str(interviewers[3].id),)


@pytest.mark.django_db
def test_busy_interviewers_and_busy_candidates_are_skipped(
    plan_job, application, interviewers, make_user, apply_as
):
    round_ = first_round(plan_job)
    round_.pool.set([interviewers[0]])
    tuesday_10 = datetime(2030, 1, 8, 10, 0, tzinfo=IST)
    other = apply_as(make_user(Role.CANDIDATE), plan_job)
    book_busy(interviewers[0], tuesday_10, application=other, round_=round_)
    slots = find_slots(round_, application.candidate, now=MONDAY)
    assert all(s.starts_at != tuesday_10 for s in slots)


@pytest.mark.django_db
def test_no_slots_flags_needs_you(plan_job, application, interviewers):
    round_ = first_round(plan_job)
    round_.pool.set([])
    interview = new_interview(application, round_)
    assert coordinator.propose(interview, now=MONDAY) == []
    interview.refresh_from_db()
    assert interview.attention == Attention.NO_SLOTS
    row = HiraActivity.objects.get(action="no_slots", interview=interview)
    assert row.needs_you
    assert Notification.objects.filter(user=plan_job.created_by, kind="hira_needs_you").exists()


# ------------------------------------------------------- moving to Interview
@pytest.mark.django_db
def test_moving_to_interview_makes_hira_offer_slots_and_email_a_link(plan_job, apply_as, users, to_interview):
    application = to_interview(apply_as(users["candidate"], plan_job))
    interview = application.interviews.get()
    open_slots = interview.slots.filter(status=SlotStatus.OPEN)
    assert rules.MIN_SLOTS <= open_slots.count() <= rules.MAX_SLOTS
    assert HiraActivity.objects.filter(action="slots_proposed", interview=interview).exists()
    mail = EmailOutbox.objects.filter(to_email=users["candidate"].email, kind="interview_slots").get()
    assert "/schedule/" in mail.body
    note = Notification.objects.get(user=users["candidate"], kind="interview_slots")
    assert "/schedule/" not in note.link  # the single-use link only travels by email


@pytest.mark.django_db
def test_let_hira_schedule_off_means_no_proposal(plan_job, apply_as, users, to_interview):
    InterviewPlan.objects.filter(job=plan_job).update(hira_enabled=False)
    application = to_interview(apply_as(users["candidate"], plan_job))
    assert not application.interviews.exists()


@pytest.mark.django_db
def test_rejecting_cancels_interviews_and_releases_time(plan_job, apply_as, users, to_interview):
    from applications.services import move_application

    application = to_interview(apply_as(users["candidate"], plan_job))
    interview = application.interviews.get()
    slot = interview.slots.first()
    coordinator.confirm(interview, slot.id)
    move_application(application, "rejected", plan_job.created_by, reason="interview_outcome", silent=True)
    interview.refresh_from_db()
    assert interview.status == InterviewStatus.CANCELLED
    assert not TimeClaim.objects.filter(interview=interview, active=True).exists()


# ---------------------------------------------------------------- holds, booking
@pytest.mark.django_db
def test_hold_then_confirm_books_everyone_and_sends_ics(plan_job, application, interviewers):
    interview = new_interview(application, first_round(plan_job))
    coordinator.propose(interview, now=MONDAY)
    slot = interview.slots.order_by("starts_at").first()
    held = coordinator.hold(interview, slot.id, now=MONDAY)
    assert held.status == SlotStatus.HELD and held.held_until == MONDAY + timedelta(
        minutes=rules.HOLD_MINUTES
    )
    assert TimeClaim.objects.filter(interview=interview, kind=ClaimKind.HOLD, active=True).count() == 2
    coordinator.confirm(interview, slot.id, now=MONDAY + timedelta(minutes=5))
    interview.refresh_from_db()
    assert interview.status == InterviewStatus.SCHEDULED
    assert interview.starts_at == slot.starts_at and interview.scheduled_by == "hira"
    assert interview.meeting_link.startswith("https://meet.example/simulated/")
    assert interview.scorecard_due_at == interview.ends_at + rules.SCORECARD_DUE
    active = TimeClaim.objects.filter(interview=interview, active=True)
    assert {c.kind for c in active} == {ClaimKind.INTERVIEW} and active.count() == 2
    assert not interview.slots.filter(status=SlotStatus.OPEN).exists()
    invite = EmailOutbox.objects.get(to_email=application.candidate.email, kind="interview_scheduled")
    assert invite.attachment_name == "interview.ics" and "BEGIN:VEVENT" in invite.attachment
    interviewer = interview.assignments.get().interviewer
    assert EmailOutbox.objects.filter(to_email=interviewer.email, kind="interview_scheduled").exists()
    assert HiraActivity.objects.filter(action="interview_scheduled", interview=interview).exists()
    assert AuditLog.objects.filter(action="hira.interview_scheduled", target_id=str(interview.id)).exists()


@pytest.mark.django_db
def test_a_hold_blocks_other_candidates_until_it_expires(
    plan_job, application, interviewers, make_user, apply_as
):
    round_ = first_round(plan_job)
    round_.pool.set([interviewers[0]])
    first = new_interview(application, round_)
    coordinator.propose(first, now=MONDAY)
    slot = first.slots.order_by("starts_at").first()
    coordinator.hold(first, slot.id, now=MONDAY)

    rival = new_interview(apply_as(make_user(Role.CANDIDATE), plan_job), round_)
    same_time = SlotOffer.objects.create(
        interview=rival,
        starts_at=slot.starts_at,
        ends_at=slot.ends_at,
        interviewer_ids=[str(interviewers[0].id)],
    )
    with pytest.raises(claims.SlotTaken):
        coordinator.hold(rival, same_time.id, now=MONDAY + timedelta(minutes=10))
    # The lost slot stops being offered and HIRA offers fresh times instead.
    same_time.refresh_from_db()
    assert same_time.status == SlotStatus.WITHDRAWN
    assert rival.slots.filter(status=SlotStatus.OPEN).exists()
    # After 30 minutes the hold lapses and the time is free again.
    later = MONDAY + timedelta(minutes=rules.HOLD_MINUTES + 1)
    assert coordinator.expire_holds(later) == 1
    again = SlotOffer.objects.create(
        interview=rival,
        starts_at=slot.starts_at,
        ends_at=slot.ends_at,
        interviewer_ids=[str(interviewers[0].id)],
    )
    coordinator.hold(rival, again.id, now=later)
    slot.refresh_from_db()
    assert slot.status == SlotStatus.OPEN
    assert HiraActivity.objects.filter(action="hold_expired", interview=first).exists()


@pytest.mark.django_db
def test_a_candidate_is_never_double_booked(plan_job, make_job, interviewers, users, apply_as):
    other_job = make_job(title="Data Engineer")
    first = new_interview(apply_as(users["candidate"], plan_job), first_round(plan_job))
    coordinator.propose(first, now=MONDAY)
    slot = first.slots.order_by("starts_at").first()
    coordinator.confirm(first, slot.id, now=MONDAY)
    # Another job, a different interviewer, the same time: the candidate is busy.
    plan = coordinator.build_default_plan(other_job)
    round_ = plan.rounds.get(order=1)
    second = new_interview(apply_as(users["candidate"], other_job), round_)
    busy_interviewer = str(first.assignments.get().interviewer_id)
    free = next(str(p.id) for p in interviewers if str(p.id) != busy_interviewer)
    clash = SlotOffer.objects.create(
        interview=second, starts_at=slot.starts_at, ends_at=slot.ends_at, interviewer_ids=[free]
    )
    with pytest.raises(claims.SlotTaken):
        coordinator.confirm(second, clash.id, now=MONDAY)


@pytest.mark.django_db
def test_manual_scheduling_uses_the_same_clash_checks(
    plan_job, application, interviewers, users, make_user, apply_as
):
    InterviewPlan.objects.filter(job=plan_job).update(hira_enabled=False)
    round_ = first_round(plan_job)
    start = datetime(2030, 1, 8, 11, 0, tzinfo=IST)
    other = apply_as(make_user(Role.CANDIDATE), plan_job)
    book_busy(interviewers[0], start, application=other, round_=round_)
    with pytest.raises(claims.SlotTaken):
        coordinator.schedule_manually(
            application, round_, start, [interviewers[0].id], users["recruiter"], now=MONDAY
        )
    BlockedTime.objects.create(user=interviewers[1], starts_at=start, ends_at=start + timedelta(hours=3))
    with pytest.raises(claims.SlotTaken):
        coordinator.schedule_manually(
            application,
            round_,
            start + timedelta(hours=1),
            [interviewers[1].id],
            users["recruiter"],
            now=MONDAY,
        )
    interview = coordinator.schedule_manually(
        application, round_, start, [interviewers[2].id], users["recruiter"], now=MONDAY
    )
    assert interview.status == InterviewStatus.SCHEDULED and interview.scheduled_by == "manual"
    assert HiraActivity.objects.filter(action="manual_scheduled", interview=interview).exists()


# -------------------------------------------------------- PostgreSQL guarantees
@postgres_only
@pytest.mark.django_db
def test_exclusion_constraint_rejects_overlapping_claims(plan_job, application, interviewers):
    interview = new_interview(application, first_round(plan_job))
    start = datetime(2030, 1, 8, 10, 0, tzinfo=IST)
    TimeClaim.objects.create(
        person=interviewers[0],
        interview=interview,
        kind="interview",
        starts_at=start,
        ends_at=start + timedelta(hours=1),
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        TimeClaim.objects.create(
            person=interviewers[0],
            interview=interview,
            kind="hold",
            starts_at=start + timedelta(minutes=30),
            ends_at=start + timedelta(minutes=90),
        )
    # Touching ends do not overlap, and inactive claims are ignored.
    TimeClaim.objects.create(
        person=interviewers[0],
        interview=interview,
        kind="interview",
        starts_at=start + timedelta(hours=1),
        ends_at=start + timedelta(hours=2),
    )
    TimeClaim.objects.create(
        person=interviewers[0],
        interview=interview,
        kind="hold",
        active=False,
        starts_at=start,
        ends_at=start + timedelta(hours=1),
    )


@postgres_only
@pytest.mark.django_db(transaction=True, serialized_rollback=True)
def test_concurrent_bookings_for_the_same_interviewer_only_one_wins(
    plan_job, interviewers, make_user, apply_as
):
    round_ = first_round(plan_job)
    round_.pool.set([interviewers[0]])
    start = datetime(2030, 1, 8, 10, 0, tzinfo=IST)
    contenders = []
    for _ in range(4):
        interview = new_interview(apply_as(make_user(Role.CANDIDATE), plan_job), round_)
        slot = SlotOffer.objects.create(
            interview=interview,
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            interviewer_ids=[str(interviewers[0].id)],
        )
        contenders.append((interview, slot))
    barrier = threading.Barrier(len(contenders))
    results = []

    def attempt(interview, slot):
        from django.db import connections

        try:
            barrier.wait()
            coordinator.confirm(interview, slot.id, now=MONDAY, silent=True)
            results.append("booked")
        except claims.SlotTaken:
            results.append("taken")
        finally:
            connections.close_all()

    threads = [threading.Thread(target=attempt, args=c) for c in contenders]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["booked", "taken", "taken", "taken"]
    assert TimeClaim.objects.filter(person=interviewers[0], active=True).count() == 1


# --------------------------------------------------------------------- reminders
@pytest.mark.django_db
def test_reminders_go_out_once_at_24h_and_1h(plan_job, application, interviewers):
    interview = new_interview(application, first_round(plan_job))
    coordinator.propose(interview, now=MONDAY)
    slot = interview.slots.order_by("starts_at").first()
    coordinator.confirm(interview, slot.id, now=MONDAY, silent=True)
    start = slot.starts_at
    candidate = application.candidate

    def reminders():
        return Notification.objects.filter(kind="interview_reminder", user=candidate).count()

    assert coordinator.send_reminders(start - timedelta(hours=25)) == 0
    assert coordinator.send_reminders(start - timedelta(hours=23)) == 1
    assert coordinator.send_reminders(start - timedelta(hours=22)) == 0  # not twice
    assert reminders() == 1
    interviewer = interview.assignments.get().interviewer
    assert Notification.objects.filter(kind="interview_reminder", user=interviewer).count() == 1
    assert coordinator.send_reminders(start - timedelta(minutes=50)) == 1
    assert coordinator.send_reminders(start - timedelta(minutes=10)) == 0
    assert reminders() == 2
    assert coordinator.send_reminders(start + timedelta(minutes=5)) == 0
    assert HiraActivity.objects.filter(action="reminder_sent", interview=interview).count() == 2


@pytest.mark.django_db
def test_late_booking_skips_the_24h_reminder(plan_job, application, interviewers, users):
    round_ = first_round(plan_job)
    start = datetime(2030, 1, 8, 11, 0, tzinfo=IST)
    interview = coordinator.schedule_manually(
        application, round_, start, [interviewers[0].id], users["recruiter"], now=start - timedelta(hours=3)
    )
    assert coordinator.send_reminders(start - timedelta(hours=2)) == 0
    assert coordinator.send_reminders(start - timedelta(minutes=30)) == 1
    interview.refresh_from_db()
    assert interview.reminder_24h_sent_at is None and interview.reminder_1h_sent_at is not None


@pytest.mark.django_db
def test_tick_runs_every_interview_task(plan_job, application, interviewers, settings):
    from core.tasks import run_tick

    result = run_tick(MONDAY)
    assert set(result["tasks"]) >= {
        "holds_released",
        "interviews_completed",
        "reminders_sent",
        "scorecards_chased",
        "offers_expired",
    }


# -------------------------------------------------------------------- reschedule
def _book(interview, now):
    slot = interview.slots.filter(status=SlotStatus.OPEN).order_by("starts_at").first()
    return coordinator.confirm(interview, slot.id, now=now, silent=True)


@pytest.mark.django_db
def test_candidate_can_reschedule_twice_then_the_recruiter_is_asked(plan_job, application, interviewers):
    interview = new_interview(application, first_round(plan_job))
    coordinator.propose(interview, now=MONDAY, silent=True)
    _book(interview, MONDAY)
    first_start = Interview.objects.get(pk=interview.pk).starts_at
    for n in (1, 2):
        coordinator.reschedule(interview, now=MONDAY, silent=True)
        interview.refresh_from_db()
        assert interview.status == InterviewStatus.PENDING and interview.reschedule_count == n
        assert not TimeClaim.objects.filter(interview=interview, active=True).exists()
        if n == 1:
            assert first_start not in set(
                interview.slots.filter(status=SlotStatus.OPEN).values_list("starts_at", flat=True)
            )
        _book(interview, MONDAY)
    with pytest.raises(ValidationError) as excinfo:
        coordinator.reschedule(interview, now=MONDAY, silent=True)
    assert "rescheduled twice" in str(excinfo.value.detail)
    interview.refresh_from_db()
    assert interview.status == InterviewStatus.SCHEDULED and interview.attention == Attention.RESCHEDULE_LIMIT
    assert (
        HiraActivity.objects.filter(action="reschedule_limit", interview=interview, needs_you=True).count()
        == 1
    )
    assert HiraActivity.objects.filter(action="reschedule_handled", interview=interview).count() == 2


@pytest.mark.django_db
def test_no_candidate_reschedule_within_12_hours(plan_job, application, interviewers):
    interview = new_interview(application, first_round(plan_job))
    coordinator.propose(interview, now=MONDAY, silent=True)
    _book(interview, MONDAY)
    interview.refresh_from_db()
    with pytest.raises(ValidationError) as excinfo:
        coordinator.reschedule(interview, now=interview.starts_at - timedelta(hours=11))
    assert "12 hours" in str(excinfo.value.detail)


# ------------------------------------------------------- declines and no-shows
@pytest.mark.django_db
def test_decline_finds_a_free_replacement_from_the_pool(plan_job, application, interviewers):
    interview = new_interview(application, first_round(plan_job))
    coordinator.propose(interview, now=MONDAY, silent=True)
    _book(interview, MONDAY)
    original = interview.assignments.get().interviewer
    result = coordinator.decline(interview, original, reason="Travelling", now=MONDAY)
    assert result["replaced"] is True
    interview.refresh_from_db()
    assert interview.status == InterviewStatus.SCHEDULED
    current = interview.assignments.get(status=AssignmentStatus.ASSIGNED).interviewer
    assert current != original
    assert TimeClaim.objects.filter(interview=interview, person=current, active=True).exists()
    assert not TimeClaim.objects.filter(interview=interview, person=original, active=True).exists()
    assert HiraActivity.objects.filter(action="interviewer_replaced", interview=interview).exists()


@pytest.mark.django_db
def test_decline_without_replacement_offers_new_slots_and_needs_you(plan_job, application, interviewers):
    round_ = first_round(plan_job)
    round_.pool.set([interviewers[0]])
    interview = new_interview(application, round_)
    coordinator.propose(interview, now=MONDAY, silent=True)
    _book(interview, MONDAY)
    coordinator.decline(interview, interviewers[0], now=MONDAY, silent=True)
    interview.refresh_from_db()
    assert interview.status == InterviewStatus.PENDING
    assert interview.attention == Attention.REPLACEMENT_FAILED
    assert interview.reschedule_count == 0  # not counted against the candidate
    assert HiraActivity.objects.filter(action="replacement_failed", needs_you=True).exists()


@pytest.mark.django_db
def test_no_show_only_after_the_start(plan_job, application, interviewers):
    interview = new_interview(application, first_round(plan_job))
    coordinator.propose(interview, now=MONDAY, silent=True)
    _book(interview, MONDAY)
    interview.refresh_from_db()
    person = interview.assignments.get().interviewer
    with pytest.raises(ValidationError):
        coordinator.mark_no_show(interview, person, now=interview.starts_at - timedelta(minutes=5))
    coordinator.mark_no_show(interview, person, now=interview.starts_at + timedelta(minutes=10))
    interview.refresh_from_db()
    assert interview.status == InterviewStatus.NO_SHOW
    assert Notification.objects.filter(user=plan_job.created_by, kind="interview_no_show").exists()

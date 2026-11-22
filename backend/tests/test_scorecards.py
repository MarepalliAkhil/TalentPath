"""Scorecards: template from the job, required comments, independent feedback,
summaries, overdue chasing and the next round starting automatically."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from hira.activity import needs_you
from hira.models import HiraActivity
from interviews import coordinator, scorecards
from interviews.models import InterviewPlan, InterviewStatus, Scorecard
from notifications.models import EmailOutbox, Notification


@pytest.fixture
def application(plan_job, users, apply_as):
    """The candidate's application to the job with the two-round plan."""
    return apply_as(users["candidate"], plan_job)


def as_user(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def rounds(job):
    plan = InterviewPlan.objects.get(job=job)
    return plan.rounds.get(order=1), plan.rounds.get(order=2)


def full_card(job, rating=4, comment=""):
    keys = [c["key"] for c in scorecards.template(job)]
    return {
        "ratings": {k: rating for k in keys},
        "comments": {k: comment for k in keys} if comment else {},
        "recommendation": "yes",
        "summary": "Solid.",
    }


@pytest.mark.django_db
def test_template_is_built_from_the_job(plan_job):
    keys = [c["key"] for c in scorecards.template(plan_job)]
    assert keys == ["skill:django", "skill:python", "communication", "problem_solving"]


@pytest.mark.django_db
def test_comments_are_required_for_1_2_and_5(plan_job, application, interviewers, run_round):
    tech, _ = rounds(plan_job)
    interview = run_round(application, tech, interviewers[:1], submit=False)
    client = as_user(interviewers[0])
    for rating in (1, 2, 5):
        response = client.post(
            f"/api/interviews/{interview.id}/scorecards", full_card(plan_job, rating), format="json"
        )
        assert response.status_code == 400
        assert any(k.startswith("comments.") for k in response.data)
    missing = {**full_card(plan_job), "recommendation": ""}
    assert (
        client.post(f"/api/interviews/{interview.id}/scorecards", missing, format="json").status_code == 400
    )
    partial = full_card(plan_job)
    partial["ratings"].pop("communication")
    assert (
        client.post(f"/api/interviews/{interview.id}/scorecards", partial, format="json").status_code == 400
    )
    ok = client.post(
        f"/api/interviews/{interview.id}/scorecards",
        full_card(plan_job, 5, "Excellent design."),
        format="json",
    )
    assert ok.status_code == 201
    again = client.post(f"/api/interviews/{interview.id}/scorecards", full_card(plan_job), format="json")
    assert again.status_code == 400  # one scorecard per interviewer


@pytest.mark.django_db
def test_comments_are_encrypted_at_rest(plan_job, application, interviewers, run_round):
    from django.db import connection

    tech, _ = rounds(plan_job)
    interview = run_round(application, tech, interviewers[:1], rating=5)
    card = Scorecard.objects.get(interview=interview)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT comments FROM interviews_scorecard WHERE id = %s",
            [card.id.hex if connection.vendor == "sqlite" else card.id],
        )
        raw = cursor.fetchone()[0]
    assert raw.startswith("v1:") and "Clear evidence" not in raw


@pytest.mark.django_db
def test_feedback_stays_hidden_until_you_submit_yours(plan_job, application, interviewers, users, run_round):
    _, panel = rounds(plan_job)
    a, b = interviewers[:2]
    interview = run_round(application, panel, [a, b], submit=False)
    assert (
        as_user(a)
        .post(f"/api/interviews/{interview.id}/scorecards", full_card(plan_job), format="json")
        .status_code
        == 201
    )
    before = as_user(b).get(f"/api/interviews/{interview.id}/scorecards").data
    assert before["others_hidden"] is True and before["others"] == [] and before["mine"] is None
    assert before["summary"]["hidden"] is True and before["summary"]["criteria"] == []
    assert (
        as_user(b)
        .post(f"/api/interviews/{interview.id}/scorecards", full_card(plan_job, 3), format="json")
        .status_code
        == 201
    )
    after = as_user(b).get(f"/api/interviews/{interview.id}/scorecards").data
    assert after["others_hidden"] is False and [c["interviewer"]["id"] for c in after["others"]] == [
        str(a.id)
    ]
    for viewer in (users["recruiter"], users["hiring_manager"], users["hr_admin"]):
        seen = as_user(viewer).get(f"/api/interviews/{interview.id}/scorecards").data
        assert len(seen["others"]) == 2 and seen["others_hidden"] is False
    summary = scorecards.summary(interview, users["recruiter"])
    assert summary["submitted"] == 2 and summary["recommendations"]["yes"] == 2
    assert {c["key"]: c["average"] for c in summary["criteria"]}["communication"] == 3.5


@pytest.mark.django_db
def test_not_before_the_interview_starts(plan_job, application, interviewers, run_round):
    tech, _ = rounds(plan_job)
    interview = run_round(application, tech, interviewers[:1], submit=False, hours_ago=-5)
    response = as_user(interviewers[0]).post(
        f"/api/interviews/{interview.id}/scorecards", full_card(plan_job), format="json"
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_passing_a_round_starts_the_next_and_the_final_round_unlocks_offers(
    plan_job, apply_as, users, to_interview, interviewers
):
    application = to_interview(apply_as(users["candidate"], plan_job))
    tech, panel = rounds(plan_job)
    first = application.interviews.get(round=tech)
    slot = first.slots.order_by("starts_at").first()
    coordinator.confirm(first, slot.id, silent=True)
    first.refresh_from_db()
    person = first.assignments.get().interviewer
    later = first.ends_at + timedelta(minutes=5)
    scorecards.submit(
        first,
        person,
        now=later,
        recommendation="strong_yes",
        comments={},
        ratings={c["key"]: 4 for c in scorecards.template(plan_job)},
    )
    first.refresh_from_db()
    assert first.status == InterviewStatus.COMPLETED
    coordinator.after_scorecard(first, silent=True)
    second = application.interviews.get(round=panel)
    assert second.status == InterviewStatus.PENDING and second.slots.exists()
    assert HiraActivity.objects.filter(action="next_round", interview=second).exists()
    assert not coordinator.final_round_passed(application)


@pytest.mark.django_db
def test_negative_feedback_does_not_start_another_round(
    plan_job, application, interviewers, run_round, users
):
    from applications.services import move_application

    InterviewPlan.objects.filter(job=plan_job).update(hira_enabled=False)
    move_application(application, "screening", users["recruiter"], silent=True)
    move_application(application, "interview", users["recruiter"], silent=True)
    InterviewPlan.objects.filter(job=plan_job).update(hira_enabled=True)
    tech, _ = rounds(plan_job)
    interview = run_round(application, tech, interviewers[:1], recommendation="no")
    coordinator.after_scorecard(interview)
    assert application.interviews.count() == 1
    assert coordinator.round_outcome(interview) == "not_passed"
    assert Notification.objects.filter(user=users["recruiter"], kind="hira_needs_you").exists()


@pytest.mark.django_db
def test_overdue_scorecards_are_chased_and_flagged_after_48_hours(
    plan_job, application, interviewers, users, run_round
):
    tech, _ = rounds(plan_job)
    interview = run_round(application, tech, interviewers[:1], submit=False, hours_ago=3)
    person = interviewers[0]
    now = timezone.now()
    assert coordinator.chase_scorecards(now)["chased"] == 0  # not due yet
    due = interview.scorecard_due_at + timedelta(minutes=1)
    assert coordinator.chase_scorecards(due) == {"chased": 1, "flagged": 0}
    assert coordinator.chase_scorecards(due + timedelta(hours=1))["chased"] == 0  # once a day
    assert Notification.objects.filter(user=person, kind="scorecard_due").count() == 1
    assert EmailOutbox.objects.filter(to_email=person.email, kind="scorecard_due").count() == 1
    later = interview.ends_at + timedelta(hours=49)
    assert coordinator.chase_scorecards(later) == {"chased": 1, "flagged": 1}
    assert [r.action for r in needs_you(users["recruiter"])] == ["scorecard_overdue"]
    scorecards.submit(
        interview,
        person,
        ratings={c["key"]: 3 for c in scorecards.template(plan_job)},
        comments={},
        recommendation="yes",
    )
    assert needs_you(users["recruiter"]) == []  # resolved by the submission
    assert coordinator.chase_scorecards(later + timedelta(days=2)) == {"chased": 0, "flagged": 0}

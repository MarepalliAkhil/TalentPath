"""HIRA activity log, login briefing and the Needs you list."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role
from hira import activity
from hira.models import AppendOnlyError, HiraAction, HiraActivity
from interviews.models import Attention, Interview, InterviewPlan


def as_user(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def pending_interview(plan_job, users, apply_as):
    application = apply_as(users["candidate"], plan_job)
    round_ = InterviewPlan.objects.get(job=plan_job).rounds.get(order=1)
    return Interview.objects.create(application=application, round=round_)


def seed_log(interview, counts: dict, *, at=None):
    for action, n in counts.items():
        for _ in range(n):
            activity.log(action, interview=interview, at=at)


@pytest.mark.django_db
def test_briefing_counts_come_from_the_log(pending_interview, users):
    seed_log(
        pending_interview,
        {
            HiraAction.INTERVIEW_SCHEDULED: 5,
            HiraAction.RESCHEDULE_HANDLED: 2,
            HiraAction.SCORECARD_CHASED: 3,
            HiraAction.SLOTS_PROPOSED: 4,
        },
    )
    Interview.objects.filter(pk=pending_interview.pk).update(attention=Attention.NO_SLOTS)
    activity.log(HiraAction.NO_SLOTS, interview=pending_interview)
    data = as_user(users["recruiter"]).get("/api/hira/briefing").data
    assert data["counts"]["interview_scheduled"] == 5
    assert data["counts"]["reschedule_handled"] == 2
    assert data["counts"]["scorecard_chased"] == 3
    assert data["needs_you_count"] == 1 and data["needs_you"][0]["action"] == "no_slots"
    assert data["message"] == (
        "While you were away, HIRA scheduled 5 interviews, handled 2 reschedules and chased 3 overdue "
        "scorecards; "
        "1 item needs you."
    )
    assert data["spoken"] == data["message"]


@pytest.mark.django_db
def test_spoken_briefing_never_contains_candidate_names(pending_interview, users):
    seed_log(pending_interview, {HiraAction.INTERVIEW_SCHEDULED: 1})
    Interview.objects.filter(pk=pending_interview.pk).update(attention=Attention.NO_SLOTS)
    activity.log(HiraAction.NO_SLOTS, interview=pending_interview)
    data = as_user(users["recruiter"]).get("/api/hira/briefing").data
    name = users["candidate"].full_name
    assert name not in data["spoken"]
    assert not any(part in data["spoken"] for part in name.split())
    assert (
        "Candidate #" not in data["spoken"] and pending_interview.application.job.title not in data["spoken"]
    )


@pytest.mark.django_db
def test_marking_seen_starts_the_next_briefing_from_now(pending_interview, users):
    old = timezone.now() - timedelta(hours=3)
    seed_log(pending_interview, {HiraAction.INTERVIEW_SCHEDULED: 2}, at=old)
    client = as_user(users["recruiter"])
    assert client.get("/api/hira/briefing").data["counts"]["interview_scheduled"] == 2
    assert client.post("/api/hira/briefing").status_code == 200
    assert client.get("/api/hira/briefing").data["counts"]["interview_scheduled"] == 0
    seed_log(pending_interview, {HiraAction.INTERVIEW_SCHEDULED: 1})
    data = client.get("/api/hira/briefing").data
    assert data["counts"]["interview_scheduled"] == 1
    assert data["message"].startswith("While you were away, HIRA scheduled 1 interview;")


@pytest.mark.django_db
def test_briefing_and_activity_are_scoped_to_your_jobs(pending_interview, users, make_user):
    seed_log(pending_interview, {HiraAction.INTERVIEW_SCHEDULED: 3})
    other = as_user(make_user(Role.RECRUITER))
    assert other.get("/api/hira/briefing").data["counts"]["interview_scheduled"] == 0
    assert other.get("/api/hira/activity").data["results"] == []
    assert as_user(users["hr_admin"]).get("/api/hira/briefing").data["counts"]["interview_scheduled"] == 3
    for role in ("candidate", "hiring_manager", "employee"):
        assert as_user(users[role]).get("/api/hira/briefing").status_code == 403


@pytest.mark.django_db
def test_needs_you_items_disappear_once_fixed(pending_interview, users):
    Interview.objects.filter(pk=pending_interview.pk).update(attention=Attention.NO_SLOTS)
    activity.log(HiraAction.NO_SLOTS, interview=pending_interview)
    activity.log(HiraAction.NO_SLOTS, interview=pending_interview)  # repeated flags count once
    assert len(activity.needs_you(users["recruiter"])) == 1
    Interview.objects.filter(pk=pending_interview.pk).update(attention="")
    assert activity.needs_you(users["recruiter"]) == []


@pytest.mark.django_db
def test_activity_page_filters_kpis_and_chart_data(pending_interview, users):
    seed_log(pending_interview, {HiraAction.INTERVIEW_SCHEDULED: 2, HiraAction.REMINDER_SENT: 3})
    seed_log(pending_interview, {HiraAction.SCORECARD_CHASED: 1}, at=timezone.now() - timedelta(days=3))
    client = as_user(users["recruiter"])
    rows = client.get("/api/hira/activity").data
    assert rows["count"] == 6
    only = client.get("/api/hira/activity?action=reminder_sent").data
    assert only["count"] == 3 and {r["action"] for r in only["results"]} == {"reminder_sent"}
    assert client.get(f"/api/hira/activity?job={pending_interview.application.job_id}").data["count"] == 6
    assert client.get("/api/hira/activity?from=2000-01-01&to=2000-01-02").data["count"] == 0
    assert client.get("/api/hira/activity?from=bad").status_code == 400
    summary = client.get("/api/hira/activity/summary").data
    assert (
        summary["kpis"]["scheduled"] == 2
        and summary["kpis"]["reminders"] == 3
        and summary["kpis"]["chased"] == 1
    )
    assert len(summary["by_day"]) == 14
    assert sum(d["scheduled"] for d in summary["by_day"]) == 2
    assert sum(d["chased"] for d in summary["by_day"]) == 1


@pytest.mark.django_db
def test_activity_log_is_append_only_and_audited(pending_interview):
    from core.models import AuditLog

    row = activity.log(
        HiraAction.INTERVIEW_SCHEDULED, interview=pending_interview, reason_code="candidate_picked"
    )
    assert AuditLog.objects.filter(
        action="hira.interview_scheduled", target_id=str(pending_interview.id)
    ).exists()
    row.reason_code = "changed"
    with pytest.raises(AppendOnlyError):
        row.save()
    with pytest.raises(AppendOnlyError):
        row.delete()
    assert HiraActivity.objects.get(pk=row.pk).reason_code == "candidate_picked"

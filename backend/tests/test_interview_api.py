"""Interview endpoints: candidate slot picking, email links, interviewer views,
plans and availability, plus blind screening on the new surfaces."""

import re
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role
from interviews import tokens
from interviews.models import Interview, InterviewPlan, InterviewStatus, LinkToken, SlotStatus
from notifications.models import EmailOutbox


def as_user(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def link_from_email(candidate) -> str:
    mail = EmailOutbox.objects.filter(to_email=candidate.email, kind="interview_slots").latest("created_at")
    return re.search(r"/schedule/(\S+)", mail.body).group(1)


@pytest.fixture
def interviewing(plan_job, apply_as, users, to_interview):
    application = to_interview(apply_as(users["candidate"], plan_job))
    return application, application.interviews.get()


@pytest.mark.django_db
def test_candidate_sees_offered_slots_and_books_one(interviewing, users):
    application, interview = interviewing
    client = as_user(users["candidate"])
    rows = client.get("/api/my/interviews").data["results"]
    assert len(rows) == 1 and rows[0]["status"] == "pending"
    assert 3 <= len(rows[0]["slots"]) <= 5
    assert "candidate" not in rows[0]  # no staff-only fields
    slot = rows[0]["slots"][0]["id"]
    held = client.post(f"/api/interviews/{interview.id}/hold", {"slot": slot}, format="json")
    assert held.status_code == 200 and held.data["held_minutes"] == 30
    booked = client.post(f"/api/interviews/{interview.id}/confirm", {"slot": slot}, format="json")
    assert booked.status_code == 200 and booked.data["status"] == "scheduled"
    assert booked.data["can_reschedule"] is True and booked.data["reschedules_left"] == 2
    ics = client.get(f"/api/interviews/{interview.id}/calendar.ics")
    assert ics.status_code == 200 and ics["Content-Type"].startswith("text/calendar")
    assert b"BEGIN:VCALENDAR" in ics.content


@pytest.mark.django_db
def test_other_candidates_cannot_touch_my_interview(interviewing, make_user):
    _, interview = interviewing
    stranger = as_user(make_user(Role.CANDIDATE))
    slot = interview.slots.first().id
    assert (
        stranger.post(f"/api/interviews/{interview.id}/hold", {"slot": str(slot)}, format="json").status_code
        == 404
    )
    assert (
        stranger.post(
            f"/api/interviews/{interview.id}/confirm", {"slot": str(slot)}, format="json"
        ).status_code
        == 404
    )
    assert stranger.get(f"/api/interviews/{interview.id}/calendar.ics").status_code == 404
    assert stranger.get("/api/my/interviews").data["results"] == []


@pytest.mark.django_db
def test_email_link_works_once_without_signing_in(interviewing, users):
    application, interview = interviewing
    token = link_from_email(users["candidate"])
    anon = APIClient(enforce_csrf_checks=False)
    page = anon.get(f"/api/schedule/{token}")
    assert page.status_code == 200 and page.data["slots"]
    assert "candidate" not in page.data and users["candidate"].full_name not in str(page.data)
    slot = page.data["slots"][1]["id"]
    assert anon.post(f"/api/schedule/{token}/hold", {"slot": slot}, format="json").status_code == 200
    done = anon.post(f"/api/schedule/{token}/confirm", {"slot": slot}, format="json")
    assert done.status_code == 200 and done.data["status"] == "scheduled"
    again = anon.post(f"/api/schedule/{token}/confirm", {"slot": slot}, format="json")
    assert again.status_code == 410  # single use
    assert anon.get(f"/api/schedule/{token}").status_code == 410


@pytest.mark.django_db
def test_tampered_and_expired_links_are_refused(interviewing, users):
    _, interview = interviewing
    token = link_from_email(users["candidate"])
    anon = APIClient()
    tampered = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
    assert anon.get(f"/api/schedule/{tampered}").status_code == 400
    assert anon.get("/api/schedule/not-a-token").status_code == 400
    LinkToken.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    assert anon.get(f"/api/schedule/{token}").status_code == 410
    with pytest.raises(tokens.LinkGone):
        tokens.resolve(token)


@pytest.mark.django_db
def test_a_new_proposal_retires_older_links(interviewing, users):
    from interviews import coordinator

    _, interview = interviewing
    old = link_from_email(users["candidate"])
    coordinator.propose(interview)
    new = link_from_email(users["candidate"])
    assert old != new
    assert APIClient().get(f"/api/schedule/{old}").status_code == 410
    assert APIClient().get(f"/api/schedule/{new}").status_code == 200


@pytest.mark.django_db
def test_candidate_reschedule_via_api(interviewing, users):
    _, interview = interviewing
    client = as_user(users["candidate"])
    slot = interview.slots.order_by("starts_at").first()
    client.post(f"/api/interviews/{interview.id}/confirm", {"slot": str(slot.id)}, format="json")
    response = client.post(f"/api/interviews/{interview.id}/reschedule")
    assert response.status_code == 200
    assert response.data["status"] == "pending" and response.data["reschedules_left"] == 1
    assert response.data["slots"]


@pytest.mark.django_db
def test_interviewer_sees_assigned_interviews_and_can_decline(interviewing, users):
    _, interview = interviewing
    slot = interview.slots.order_by("starts_at").first()
    as_user(users["candidate"]).post(
        f"/api/interviews/{interview.id}/confirm", {"slot": str(slot.id)}, format="json"
    )
    person = interview.assignments.get().interviewer
    data = as_user(person).get("/api/interviews/assigned").data
    assert [r["id"] for r in data["upcoming"]] == [str(interview.id)]
    assert data["upcoming"][0]["can_decline"] is True
    other = interview.assignments.get().interviewer
    response = as_user(other).post(
        f"/api/interviews/{interview.id}/decline", {"reason": "Clash"}, format="json"
    )
    assert response.status_code == 200 and response.data["replaced"] is True
    # An employee who is not on the interview cannot act on it.
    outsider = users["employee"]
    assert as_user(outsider).post(f"/api/interviews/{interview.id}/decline").status_code == 404
    assert as_user(outsider).get(f"/api/interviews/{interview.id}/scorecards").status_code == 404


@pytest.mark.django_db
def test_recruiter_sees_rounds_and_can_ask_hira_or_schedule_by_hand(interviewing, users, interviewers):
    application, interview = interviewing
    client = as_user(users["recruiter"])
    data = client.get(f"/api/applications/{application.id}/interviews").data
    assert [r["round"]["name"] for r in data["rounds"]] == ["Technical", "Panel"]
    assert data["rounds"][0]["interview"]["status"] == "pending"
    assert data["can_schedule"] is True and data["final_round_passed"] is False
    assert client.post(f"/api/applications/{application.id}/interviews/propose").status_code == 200
    start = (interview.slots.order_by("starts_at").first().starts_at + timedelta(days=1)).isoformat()
    manual = client.post(
        f"/api/applications/{application.id}/interviews/manual",
        {
            "round_id": str(interview.round_id),
            "starts_at": start,
            "interviewer_ids": [str(interviewers[3].id)],
        },
        format="json",
    )
    assert manual.status_code == 201 and manual.data["scheduled_by"] == "manual"
    # Hiring managers read, but cannot schedule (policy) and other recruiters cannot see it (scope).
    assert (
        as_user(users["hiring_manager"]).get(f"/api/applications/{application.id}/interviews").status_code
        == 200
    )
    assert (
        as_user(users["hiring_manager"])
        .post(f"/api/applications/{application.id}/interviews/propose")
        .status_code
        == 403
    )


@pytest.mark.django_db
def test_other_recruiters_cannot_see_or_schedule(interviewing, make_user):
    application, _ = interviewing
    other = as_user(make_user(Role.RECRUITER))
    assert other.get(f"/api/applications/{application.id}/interviews").status_code == 404
    assert other.post(f"/api/applications/{application.id}/interviews/propose").status_code == 404
    assert other.get(f"/api/jobs/{application.job_id}/interview-plan").status_code == 404


@pytest.mark.django_db
def test_plan_can_be_edited_and_hira_switched_off(plan_job, users, interviewers):
    client = as_user(users["recruiter"])
    plan = client.get(f"/api/jobs/{plan_job.id}/interview-plan").data
    assert plan["hira_enabled"] is True and len(plan["rounds"]) == 2
    rounds = [
        {**plan["rounds"][1], "pool": [p["id"] for p in plan["rounds"][1]["pool"]]},
        {
            "name": "HR chat",
            "duration_minutes": 30,
            "mode": "phone",
            "interviewers_needed": 1,
            "pool": [str(users["hr_admin"].id)],
        },
    ]
    response = client.put(
        f"/api/jobs/{plan_job.id}/interview-plan", {"hira_enabled": False, "rounds": rounds}, format="json"
    )
    assert response.status_code == 200, response.data
    assert response.data["hira_enabled"] is False
    assert [r["name"] for r in response.data["rounds"]] == ["Panel", "HR chat"]
    bad = client.put(
        f"/api/jobs/{plan_job.id}/interview-plan",
        {
            "rounds": [
                {
                    "name": "Panel",
                    "duration_minutes": 50,
                    "mode": "video",
                    "interviewers_needed": 3,
                    "pool": [],
                }
            ]
        },
        format="json",
    )
    assert bad.status_code == 400
    assert (
        as_user(users["hiring_manager"])
        .put(f"/api/jobs/{plan_job.id}/interview-plan", {}, format="json")
        .status_code
        == 403
    )


@pytest.mark.django_db
def test_default_plan_is_built_from_the_job(make_job, interviewers, users):
    from interviews.coordinator import get_plan

    job = make_job(title="Default Plan Job")
    plan = get_plan(job)
    names = list(plan.rounds.values_list("name", flat=True))
    assert names == ["Technical 1", "Technical 2", "Hiring manager", "HR"]
    assert list(plan.rounds.get(name="Hiring manager").pool.all()) == [users["hiring_manager"]]
    assert set(plan.rounds.get(name="Technical 1").pool.all()) == set(interviewers)
    assert plan.rounds.get(name="Technical 2").interviewers_needed == 2


@pytest.mark.django_db
def test_availability_working_hours_and_blocks(users):
    client = as_user(users["employee"])
    data = client.get("/api/availability").data
    assert data["timezone"] == "Asia/Kolkata" and data["working_hours"]["1"] == ["10:00", "18:00"]
    ok = client.put(
        "/api/availability", {"working_hours": {"1": ["09:00", "13:00"], "2": None}}, format="json"
    )
    assert ok.status_code == 200 and ok.data["working_hours"] == {"1": ["09:00", "13:00"]}
    assert (
        client.put(
            "/api/availability", {"working_hours": {"1": ["13:00", "09:00"]}}, format="json"
        ).status_code
        == 400
    )
    assert (
        client.put(
            "/api/availability", {"working_hours": {"9": ["09:00", "10:00"]}}, format="json"
        ).status_code
        == 400
    )
    start = (timezone.now() + timedelta(days=2)).replace(microsecond=0)
    made = client.post(
        "/api/availability/blocks",
        {
            "starts_at": start.isoformat(),
            "ends_at": (start + timedelta(hours=2)).isoformat(),
            "reason": "Leave",
        },
        format="json",
    )
    assert made.status_code == 201 and len(made.data["blocked"]) == 1
    block = made.data["blocked"][0]["id"]
    assert (
        as_user(users["recruiter"]).delete(f"/api/availability/blocks/{block}").status_code == 404
    )  # not theirs
    assert client.delete(f"/api/availability/blocks/{block}").status_code == 204


@pytest.mark.django_db
def test_hr_admin_tags_interviewer_skills(users, skills):
    client = as_user(users["hr_admin"])
    response = client.patch(
        f"/api/interviewers/{users['employee'].id}",
        {"skills": [str(skills["react"].id)], "working_hours": {"5": ["10:00", "12:00"]}},
        format="json",
    )
    assert response.status_code == 200 and [s["slug"] for s in response.data["skills"]] == ["react"]
    listed = as_user(users["recruiter"]).get("/api/interviewers?skill=react").data["results"]
    assert [p["id"] for p in listed] == [str(users["employee"].id)]
    assert client.patch(f"/api/interviewers/{users['candidate'].id}", {}, format="json").status_code == 404


@pytest.mark.django_db
def test_blind_until_offer_keeps_interview_surfaces_blind(plan_job, apply_as, users, to_interview):
    plan_job.reveal_stage = "offer"
    plan_job.save()
    application = to_interview(apply_as(users["candidate"], plan_job))
    interview = application.interviews.get()
    slot = interview.slots.order_by("starts_at").first()
    as_user(users["candidate"]).post(
        f"/api/interviews/{interview.id}/confirm", {"slot": str(slot.id)}, format="json"
    )
    name = users["candidate"].full_name
    data = as_user(users["recruiter"]).get(f"/api/applications/{application.id}/interviews").data
    row = data["rounds"][0]["interview"]
    assert row["candidate"]["full_name"] is None and row["candidate"]["code"].startswith("Candidate #")
    person = Interview.objects.get(pk=interview.pk).assignments.get().interviewer
    assert name not in str(as_user(person).get("/api/interviews/assigned").data)
    invite = EmailOutbox.objects.get(to_email=person.email, kind="interview_scheduled")
    assert name not in invite.subject and name not in invite.attachment


@pytest.mark.django_db
def test_interviews_wait_at_screening(plan_job, apply_as, users):
    from applications.services import move_application

    application = apply_as(users["candidate"], plan_job)
    move_application(application, "screening", users["recruiter"], silent=True)
    assert not application.interviews.exists()
    assert not InterviewPlan.objects.filter(job=plan_job, hira_enabled=False).exists()
    response = as_user(users["recruiter"]).post(f"/api/applications/{application.id}/interviews/propose")
    assert response.status_code == 400
    assert Interview.objects.filter(status=InterviewStatus.PENDING).count() == 0
    assert SlotStatus.OPEN == "open"

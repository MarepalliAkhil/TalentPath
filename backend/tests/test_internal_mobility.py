"""Internal mobility: who sees internal jobs, one-click apply with the profile resume, the
manager is told at Interview (not at application), the same pipeline and blind screening,
and an internal hire updates the employee record without a new account."""

from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role, User
from applications.models import Application, Source
from applications.models import ApplicationStatus as S
from applications.services import move_application
from core.models import AuditLog
from hr.models import Employee, InternalMove, WorkPolicy
from interviews.models import InterviewPlan
from interviews.timeutil import today_ist
from jobs.models import Audience
from notifications.models import Notification
from offers.models import Offer, OfferStatus
from seeding.docgen import make_pdf

RESUME = ["Asha Verma", "SKILLS", "Python, Django, PostgreSQL, Docker", "Synthetic resume."]


def as_user(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def mover(team):
    """`me` (employee role, reports to the hiring manager) with a profile resume."""
    me = team["me"]
    client = as_user(me.user)
    data = make_pdf(RESUME)
    response = client.post(
        "/api/career/profile",
        {"resume": SimpleUploadedFile("cv.pdf", data, "application/pdf")},
        format="multipart",
    )
    assert response.status_code == 201
    return me


@pytest.fixture
def internal_job(make_job, users, make_user):
    """An internal-only job owned by the recruiter, with a different hiring manager than `me`'s manager."""
    other_manager = make_user(Role.HIRING_MANAGER, name="Other Manager")
    job = make_job(title="Platform Engineer", manager=other_manager)
    job.audience = Audience.INTERNAL
    job.save()
    InterviewPlan.objects.filter(job=job).update(hira_enabled=False)
    return job


@pytest.mark.django_db
def test_employees_see_internal_jobs_with_their_match_and_the_rule(mover, internal_job):
    data = as_user(mover.user).get("/api/internal/jobs").data
    job = next(j for j in data["jobs"] if j["id"] == str(internal_job.id))
    assert job["score"] >= 0 and job["band"] and job["applied"] is False
    assert data["has_resume"] is True
    assert (
        "reaches the Interview stage" in data["rule"]["text"]
        and "Nobody is told when you apply" in data["rule"]["text"]
    )
    assert data["rule"]["manager"] == mover.manager.name


@pytest.mark.django_db
def test_internal_jobs_are_hidden_from_candidates_and_the_career_site(users, internal_job):
    assert as_user(users["candidate"]).get("/api/internal/jobs").status_code == 403
    response = as_user(users["candidate"]).post(
        "/api/applications",
        {
            "job": internal_job.slug,
            "resume": SimpleUploadedFile("cv.pdf", make_pdf(RESUME), "application/pdf"),
        },
        format="multipart",
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_one_click_apply_uses_the_profile_and_the_same_pipeline(mover, internal_job, users):
    response = as_user(mover.user).post(f"/api/internal/jobs/{internal_job.id}/apply", {}, format="json")
    assert response.status_code == 201
    application = Application.objects.get(pk=response.data["id"])
    assert application.source == Source.INTERNAL and application.candidate == mover.user
    assert application.status == S.APPLIED
    assert application.fit_score is not None  # scored like any application
    # Blind screening applies: the recruiter sees a code, not the name.
    staff = as_user(users["recruiter"]).get(f"/api/applications/{application.id}").data
    assert staff["candidate"]["full_name"] is None and staff["source"] == "internal"
    again = as_user(mover.user).post(f"/api/internal/jobs/{internal_job.id}/apply", {}, format="json")
    assert again.status_code == 409
    assert AuditLog.objects.filter(action="internal.applied").exists()
    mine = as_user(mover.user).get("/api/internal/jobs").data["applications"]
    assert mine[0]["id"] == str(application.id) and mine[0]["status_label"] == "Received"


@pytest.mark.django_db
def test_apply_needs_a_profile_resume(team, internal_job):
    response = as_user(team["peers"][1].user).post(
        f"/api/internal/jobs/{internal_job.id}/apply", {}, format="json"
    )
    assert response.status_code == 400 and "resume" in response.data


@pytest.mark.django_db
def test_external_only_jobs_cannot_be_applied_to_internally(mover, make_job):
    job = make_job(title="Campus Hire")
    job.audience = Audience.EXTERNAL
    job.save()
    assert (
        as_user(mover.user).post(f"/api/internal/jobs/{job.id}/apply", {}, format="json").status_code == 404
    )


@pytest.mark.django_db
def test_manager_is_told_at_interview_not_at_application(mover, internal_job, users):
    manager = mover.manager.user
    as_user(mover.user).post(f"/api/internal/jobs/{internal_job.id}/apply", {}, format="json")
    application = Application.objects.get(candidate=mover.user, job=internal_job)
    assert not Notification.objects.filter(user=manager, kind="internal_mobility").exists()
    move_application(application, S.SCREENING, users["recruiter"], silent=True)
    assert not Notification.objects.filter(user=manager, kind="internal_mobility").exists()
    move_application(application, S.INTERVIEW, users["recruiter"], silent=True)
    note = Notification.objects.get(user=manager, kind="internal_mobility")
    assert mover.name in note.title and "Interview" in note.body
    assert AuditLog.objects.filter(action="internal.manager_informed").exists()


@pytest.mark.django_db
def test_the_notice_stage_is_configurable(mover, internal_job, users):
    WorkPolicy.objects.filter(location=mover.location).update(internal_manager_notice="offer")
    as_user(mover.user).post(f"/api/internal/jobs/{internal_job.id}/apply", {}, format="json")
    application = Application.objects.get(candidate=mover.user, job=internal_job)
    move_application(application, S.SCREENING, users["recruiter"], silent=True)
    move_application(application, S.INTERVIEW, users["recruiter"], silent=True)
    assert not Notification.objects.filter(kind="internal_mobility").exists()
    text = as_user(mover.user).get("/api/internal/jobs").data["rule"]["text"]
    assert "only if you receive an offer" in text


@pytest.fixture
def internal_offer(mover, internal_job, users):
    as_user(mover.user).post(f"/api/internal/jobs/{internal_job.id}/apply", {}, format="json")
    application = Application.objects.get(candidate=mover.user, job=internal_job)
    Application.objects.filter(pk=application.pk).update(status=S.OFFER)
    application.refresh_from_db()
    today = today_ist(timezone.now())
    offer = Offer(
        application=application,
        status=OfferStatus.SENT,
        expires_on=today + timedelta(days=5),
        created_by=users["recruiter"],
        sent_at=timezone.now(),
    )
    offer.data = {
        "designation": "Platform Engineer",
        "department": "Sales",
        "location": "Hyderabad",
        "joining_date": (today + timedelta(days=14)).isoformat(),
        "reporting_manager_id": str(internal_job.hiring_manager_id),
        "reporting_manager_name": internal_job.hiring_manager.full_name,
        "fixed_pay": 2000000,
    }
    offer.save()
    return offer


@pytest.mark.django_db
def test_employee_accepts_their_internal_offer(mover, internal_offer, team):
    client = as_user(mover.user)
    assert client.get(f"/api/offers/{internal_offer.id}").data["status"] == "sent"
    response = client.post(
        f"/api/offers/{internal_offer.id}/accept", {"typed_name": mover.name}, format="json"
    )
    assert response.status_code == 200 and response.data["status"] == "accepted"
    # Another employee cannot see it.
    assert as_user(team["peers"][1].user).get(f"/api/offers/{internal_offer.id}").status_code == 404


@pytest.mark.django_db
def test_internal_hire_updates_the_record_without_a_new_account(mover, internal_offer, users, org):
    Offer.objects.filter(pk=internal_offer.pk).update(status=OfferStatus.ACCEPTED)
    users_before = User.objects.count()
    code, joined = mover.code, mover.joined_on
    response = as_user(users["recruiter"]).post(f"/api/offers/{internal_offer.id}/hire", {}, format="json")
    assert response.status_code == 201, response.data
    mover.refresh_from_db()
    assert User.objects.count() == users_before  # no new account
    assert Employee.objects.filter(user=mover.user).count() == 1
    assert mover.code == code and mover.joined_on == joined  # same record, same ID
    assert mover.department == org["department2"] and mover.designation == "Platform Engineer"
    assert str(mover.manager.user_id) == internal_offer.data["reporting_manager_id"]
    mover.user.refresh_from_db()
    assert mover.user.role == Role.EMPLOYEE  # no role change
    move = InternalMove.objects.get(employee=mover)
    assert move.from_department == "Engineering" and move.to_department == "Sales"
    assert AuditLog.objects.filter(action="onboarding.internal_move").exists()
    assert not AuditLog.objects.filter(action="users.role_changed").exists()
    internal_offer.application.refresh_from_db()
    assert internal_offer.application.status == S.HIRED

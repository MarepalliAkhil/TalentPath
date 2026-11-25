"""Prompt 1, part D: the multi-step application form, drafts, screening questions, the
declarations, and what recruiters see (D-83)."""

import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from rest_framework.test import APIClient

from accounts.models import Profile
from applications.models import Application, ApplicationDraft, ApplicationForm
from core.models import AuditLog

from .conftest import application_form


def as_user(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def apply(client, job, pdf_bytes, form=None, resume=True, **extra):
    data = {"job": job.slug, "form": form if form is not None else application_form(), **extra}
    if resume:
        data["resume"] = SimpleUploadedFile("cv.pdf", pdf_bytes, "application/pdf")
    return client.post("/api/applications", data, format="multipart")


@pytest.fixture
def questions_job(make_job):
    job = make_job(title="Support Engineer")
    job.screening_questions = [
        {
            "id": "q1",
            "text": "Are you comfortable with rotational shifts?",
            "kind": "yes_no",
            "required": True,
        },
        {"id": "q2", "text": "Years of Linux administration?", "kind": "number", "required": True},
        {"id": "q3", "text": "Anything else we should know?", "kind": "text", "required": False},
    ]
    job.save()
    return job


def test_a_complete_form_creates_the_application_with_the_form(users, open_job, pdf_bytes):
    response = apply(as_user(users["candidate"]), open_job, pdf_bytes)
    assert response.status_code == 201, response.data
    form = ApplicationForm.objects.get(application_id=response.data["id"])
    data = json.loads(form.data)
    assert data["personal"]["full_name"] == users["candidate"].full_name  # identity from the account
    assert data["personal"]["email"] == users["candidate"].email
    assert data["compensation"]["expected_ctc_lpa"] == "6.5"
    assert form.terms_version == "2026-11" and form.declared_at is not None
    assert AuditLog.objects.filter(action="applications.create", meta__terms="2026-11").exists()


def test_the_form_is_stored_encrypted(users, open_job, pdf_bytes):
    response = apply(as_user(users["candidate"]), open_job, pdf_bytes)
    form = ApplicationForm.objects.get(application_id=response.data["id"])
    pk = form.pk.hex if connection.vendor == "sqlite" else form.pk
    with connection.cursor() as cursor:
        cursor.execute("SELECT data FROM applications_applicationform WHERE id = %s", [pk])
        (raw,) = cursor.fetchone()
    assert raw.startswith("v1:") and "Lakeview" not in raw and "6.5" not in raw


@pytest.mark.parametrize(
    "section,patch,field",
    [
        ("declarations", {"info_true": True, "accept_terms": False}, "accept_terms"),
        ("declarations", {"info_true": False, "accept_terms": True}, "info_true"),
        (
            "compensation",
            {
                "current_ctc_lpa": "-1",
                "expected_ctc_lpa": "5",
                "notice_period": "30",
                "earliest_joining": "2030-01-01",
            },
            "current_ctc_lpa",
        ),
        (
            "compensation",
            {
                "current_ctc_lpa": "4",
                "expected_ctc_lpa": "5",
                "notice_period": "45",
                "earliest_joining": "2030-01-01",
            },
            "notice_period",
        ),
        (
            "compensation",
            {
                "current_ctc_lpa": "4",
                "expected_ctc_lpa": "5",
                "notice_period": "30",
                "earliest_joining": "2001-01-01",
            },
            "earliest_joining",
        ),
        (
            "education",
            {
                "highest_qualification": "Bachelor's degree",
                "college": "X College",
                "branch": "CSE",
                "graduation_year": 2021,
                "score_type": "cgpa",
                "score": "11",
                "tenth_percentage": "90",
                "twelfth_percentage": "90",
            },
            "score",
        ),
        ("experience", {"status": "experienced", "roles": [], "total_years": "2"}, "roles"),
        (
            "experience",
            {
                "status": "experienced",
                "roles": [{"company": "Kestrel", "title": "Dev", "start": "2024-05", "end": "2023-01"}],
                "total_years": "1",
            },
            "end",
        ),
    ],
)
def test_form_validation(users, open_job, pdf_bytes, section, patch, field):
    response = apply(
        as_user(users["candidate"]), open_job, pdf_bytes, form=application_form(**{section: patch})
    )
    assert response.status_code == 400 and field in str(response.data), response.data
    assert not Application.objects.exists()


def test_screening_questions_are_required_and_typed(users, questions_job, pdf_bytes):
    client = as_user(users["candidate"])
    missing = apply(client, questions_job, pdf_bytes, form=application_form(answers={"q1": "yes"}))
    assert missing.status_code == 400 and "q2" in str(missing.data)
    wrong = apply(
        client, questions_job, pdf_bytes, form=application_form(answers={"q1": "maybe", "q2": "two"})
    )
    assert wrong.status_code == 400 and "q1" in str(wrong.data) and "q2" in str(wrong.data)
    ok = apply(client, questions_job, pdf_bytes, form=application_form(answers={"q1": "Yes", "q2": "3.0"}))
    assert ok.status_code == 201, ok.data
    data = json.loads(ApplicationForm.objects.get(application_id=ok.data["id"]).data)
    assert data["answers"] == {"q1": "yes", "q2": "3"}


def test_recruiters_define_screening_questions_per_job(users, open_job):
    recruiter = as_user(users["recruiter"])
    response = recruiter.patch(
        f"/api/jobs/{open_job.id}",
        {"screening_questions": [{"text": "Are you comfortable with rotational shifts?", "kind": "yes_no"}]},
        format="json",
    )
    assert response.status_code == 200, response.data
    assert response.data["screening_questions"] == [
        {
            "id": "q1",
            "text": "Are you comfortable with rotational shifts?",
            "kind": "yes_no",
            "required": True,
        }
    ]
    bad = recruiter.patch(
        f"/api/jobs/{open_job.id}", {"screening_questions": [{"text": "Hi?", "kind": "essay"}]}, format="json"
    )
    assert bad.status_code == 400


def test_the_profile_resume_can_be_used_instead_of_a_new_upload(users, open_job, pdf_bytes):
    client = as_user(users["candidate"])
    no_resume = apply(client, open_job, pdf_bytes, resume=False)
    assert no_resume.status_code == 400 and "resume" in no_resume.data
    client.post(
        "/api/career/profile",
        {"resume": SimpleUploadedFile("mine.pdf", pdf_bytes, "application/pdf")},
        format="multipart",
    )
    form = json.loads(application_form())
    form["use_profile_resume"] = True
    ok = apply(client, open_job, pdf_bytes, form=json.dumps(form), resume=False)
    assert ok.status_code == 201, ok.data
    assert Application.objects.get(pk=ok.data["id"]).resume_filename == "mine.pdf"


def test_date_of_birth_from_the_form_becomes_a_locked_profile_field(users, open_job, make_job, pdf_bytes):
    client = as_user(users["candidate"])
    assert apply(client, open_job, pdf_bytes).status_code == 201
    assert Profile.objects.get(user=users["candidate"]).date_of_birth == "1999-04-12"
    # A later form cannot change it: the profile value wins.
    other = make_job(title="Second Role")
    form = json.loads(application_form())
    form["personal"]["date_of_birth"] = "1980-01-01"
    response = apply(client, other, pdf_bytes, form=json.dumps(form))
    assert response.status_code == 201
    assert (
        json.loads(ApplicationForm.objects.get(application_id=response.data["id"]).data)["personal"][
            "date_of_birth"
        ]
        == "1999-04-12"
    )


def test_drafts_save_resume_and_disappear_after_applying(users, open_job, pdf_bytes):
    client = as_user(users["candidate"])
    url = f"/api/applications/drafts/{open_job.slug}"
    context = client.get(url).data
    assert context["draft"] is None and context["prefill"]["personal"]["email"] == users["candidate"].email
    assert context["terms_version"] == "2026-11"
    saved = client.put(url, {"data": {"personal": {"current_city": "Pune"}}, "step": 2}, format="json")
    assert saved.status_code == 200 and saved.data["step"] == 2
    assert client.get(url).data["draft"] == {
        "data": {"personal": {"current_city": "Pune"}},
        "step": 2,
        "saved_at": saved.data["saved_at"],
    }
    pk = ApplicationDraft.objects.get().pk
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT data FROM applications_applicationdraft WHERE id = %s",
            [pk.hex if connection.vendor == "sqlite" else pk],
        )
        assert "Pune" not in cursor.fetchone()[0]
    assert as_user(users["employee"]).get(url).status_code == 403
    assert apply(client, open_job, pdf_bytes).status_code == 201
    assert not ApplicationDraft.objects.exists()
    assert client.get(url).data["already_applied"] is True


def test_recruiters_see_compensation_beside_the_score_and_identity_stays_blind(users, open_job, pdf_bytes):
    assert open_job.blind_screening
    response = apply(as_user(users["candidate"]), open_job, pdf_bytes)
    detail = as_user(users["recruiter"]).get(f"/api/applications/{response.data['id']}").data
    details = detail["candidate_details"]
    assert details["compensation"]["expected_ctc_lpa"] == "6.5"
    assert details["compensation"]["notice_period"] == "Immediate"
    assert "compensation" not in json.dumps(detail["fit"]) and "ctc" not in json.dumps(detail["fit"]).lower()
    assert details["blind"] is True
    assert "personal" not in details and "education" not in details  # identity and college hidden while blind
    assert "Lakeview" not in json.dumps(detail)

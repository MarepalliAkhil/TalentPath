"""Prompt 1, parts B and C: profiles for every role, locked fields, password, photo,
notification preferences, and registration with a required resume (D-81, D-82)."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from rest_framework.test import APIClient

from accounts.models import Profile, Role, User
from core.models import AuditLog
from growth.models import CareerProfile, ResumeVersion
from notifications.models import EmailOutbox, Notification
from seeding.docgen import make_pdf

from .conftest import PASSWORD, ROLES

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
RESUME = [
    "Asha Verma",
    "asha.verma@mail.test | +91 98480 12345 | linkedin.com/in/asha-verma | github.com/ashav",
    "Portfolio: https://asha-portfolio.example/work",
    "SKILLS",
    "Python, Django, PostgreSQL, React",
    "EXPERIENCE",
    "Backend Engineer, Brightleaf Analytics  Jan 2023 - Present",
    "- Built the billing service in Django.",
    "EDUCATION",
    "B.Tech Computer Science, Lakeview University, 2022, CGPA 8.6/10",
]


def db_id(value):
    """UUIDs as the database stores them (SQLite in the build sandbox keeps 32 hex digits)."""
    return value.hex if connection.vendor == "sqlite" else value


def as_user(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.mark.parametrize("role", ROLES)
def test_every_role_reads_and_edits_their_own_profile(users, role):
    client = as_user(users[role])
    data = client.get("/api/profile").data
    assert data["email"] == users[role].email and data["locked"]["email"] is True
    response = client.patch(
        "/api/profile",
        {
            "headline": "Hello",
            "phone": "+91 90000 11111",
            "github_url": "github.com/me",
            "skills": ["Python", "python", "SQL"],
        },
        format="json",
    )
    assert response.status_code == 200, response.data
    assert response.data["github_url"] == "https://github.com/me"
    assert response.data["skills"] == ["Python", "SQL"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("email", "new@corp.test"),
        ("full_name", "Someone Else"),
        ("role", "hr"),
        ("employee_code", "LW9999"),
        ("joined_on", "2020-01-01"),
    ],
)
def test_locked_fields_cannot_be_changed_by_the_person(users, field, value):
    response = as_user(users["employee"]).patch("/api/profile", {field: value}, format="json")
    assert response.status_code == 400 and field in response.data
    users["employee"].refresh_from_db()
    assert users["employee"].role == Role.EMPLOYEE


def test_date_of_birth_can_be_set_once_then_it_is_locked(users):
    client = as_user(users["candidate"])
    first = client.patch("/api/profile", {"date_of_birth": "2000-05-17"}, format="json")
    assert first.status_code == 200 and first.data["locked"]["date_of_birth"] is True
    again = client.patch("/api/profile", {"date_of_birth": "1990-01-01"}, format="json")
    assert again.status_code == 400
    profile = Profile.objects.get(user=users["candidate"])
    assert profile.date_of_birth == "2000-05-17"
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT date_of_birth, education FROM accounts_profile WHERE user_id = %s",
            [db_id(users["candidate"].id)],
        )
        raw_dob, _ = cursor.fetchone()
    assert raw_dob.startswith("v1:") and "2000" not in raw_dob


def test_education_and_experience_rows_are_stored_encrypted(users):
    client = as_user(users["candidate"])
    rows = {
        "education": [
            {"qualification": "B.Tech", "college": "Lakeview University", "year": "2022", "score": "8.6"}
        ],
        "experience": [
            {
                "title": "Backend Engineer",
                "company": "Brightleaf Analytics",
                "start": "2023-01",
                "end": "present",
            }
        ],
    }
    response = client.patch("/api/profile", rows, format="json")
    assert response.status_code == 200 and response.data["education"][0]["college"] == "Lakeview University"
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT education, experience FROM accounts_profile WHERE user_id = %s",
            [db_id(users["candidate"].id)],
        )
        edu, exp = cursor.fetchone()
    assert "Lakeview" not in edu and "Brightleaf" not in exp


def test_password_change_needs_the_current_password_and_signs_out_other_devices(users):
    user = users["recruiter"]
    other = APIClient()
    assert (
        other.post("/api/auth/login", {"email": user.email, "password": PASSWORD}, format="json").status_code
        == 200
    )
    client = APIClient()
    client.post("/api/auth/login", {"email": user.email, "password": PASSWORD}, format="json")
    wrong = client.post(
        "/api/profile/password",
        {"current_password": "nope", "new_password": "Another-Strong-2026"},
        format="json",
    )
    assert wrong.status_code == 400 and "current_password" in wrong.data
    weak = client.post(
        "/api/profile/password", {"current_password": PASSWORD, "new_password": "password"}, format="json"
    )
    assert weak.status_code == 400
    done = client.post(
        "/api/profile/password",
        {"current_password": PASSWORD, "new_password": "Another-Strong-2026"},
        format="json",
    )
    assert done.status_code == 200
    user.refresh_from_db()
    assert user.check_password("Another-Strong-2026")
    assert other.post("/api/auth/refresh").status_code == 401  # the other device's session is gone
    assert client.get("/api/auth/me").status_code == 200  # this device got fresh cookies
    assert EmailOutbox.objects.filter(to_email=user.email, kind="password_changed").exists()
    assert AuditLog.objects.filter(action="profile.password_changed").exists()


def test_profile_photo_upload_checks_the_image_and_stays_private(users):
    client = as_user(users["employee"])
    fake = SimpleUploadedFile("me.png", b"MZ\x90\x00" + b"0" * 50, "image/png")
    assert client.post("/api/profile/photo", {"photo": fake}, format="multipart").status_code == 400
    big = SimpleUploadedFile("me.png", PNG + b"0" * (2 * 1024 * 1024), "image/png")
    assert client.post("/api/profile/photo", {"photo": big}, format="multipart").status_code == 400
    ok = client.post(
        "/api/profile/photo", {"photo": SimpleUploadedFile("me.png", PNG, "image/png")}, format="multipart"
    )
    assert ok.status_code == 201 and ok.data["has_photo"] is True
    photo = client.get("/api/profile/photo")
    assert photo.status_code == 200 and photo["Content-Type"] == "image/png" and photo.content == PNG
    assert "no-store" in photo["Cache-Control"]
    assert client.delete("/api/profile/photo").status_code == 204
    assert client.get("/api/profile/photo").status_code == 404


def test_notification_preferences_switch_off_emails_but_not_the_bell(users):
    from notifications.services import notify

    user = users["employee"]
    client = as_user(user)
    response = client.put("/api/profile/notifications", {"prefs": {"leave": False}}, format="json")
    assert response.status_code == 200 and response.data["notification_prefs"]["leave"] is False
    assert (
        client.put("/api/profile/notifications", {"prefs": {"spam": False}}, format="json").status_code == 400
    )
    notify(user, kind="leave_decided", title="Leave approved", body="Your leave was approved.", link="/leave")
    notify(user, kind="offer_sent", title="Offer", body="An offer.", link="/offers")
    assert Notification.objects.filter(user=user, kind="leave_decided").exists()
    assert not EmailOutbox.objects.filter(to_email=user.email, kind="leave_decided").exists()
    assert EmailOutbox.objects.filter(to_email=user.email, kind="offer_sent").exists()


def test_account_emails_cannot_be_switched_off(users):
    from notifications.services import wants_email

    profile = users["candidate"].profile
    profile.notification_prefs = {
        key: False
        for key in ("applications", "interviews", "offers", "onboarding", "leave", "payroll", "team")
    }
    profile.save()
    assert wants_email(users["candidate"], "password_reset") is True
    assert wants_email(users["candidate"], "application_status") is False


def test_profile_lists_resume_history(users):
    client = as_user(users["candidate"])
    for extra in ([], ["PROJECTS", "A dashboard."]):
        client.post(
            "/api/career/profile",
            {"resume": SimpleUploadedFile("cv.pdf", make_pdf(RESUME + extra), "application/pdf")},
            format="multipart",
        )
    versions = client.get("/api/profile").data["resume_versions"]
    assert len(versions) == 2 and [v["current"] for v in versions] == [True, False]


# ---------------------------------------------------------------- registration (part C)
def register(client, resume=None, **extra):
    data = {
        "full_name": "Asha Verma",
        "email": "asha@new.test",
        "password": "Sturdy-Pass-123",
        "accept_terms": "true",
        **extra,
    }
    if resume is not None:
        data["resume"] = resume
    return client.post("/api/auth/register", data, format="multipart")


@pytest.mark.django_db
def test_registration_requires_a_resume():
    response = register(APIClient())
    assert response.status_code == 400 and "resume" in response.data
    assert not User.objects.filter(email="asha@new.test").exists()


@pytest.mark.django_db
@pytest.mark.parametrize("data,name", [(b"MZ\x90\x00" + b"0" * 100, "cv.pdf"), (b"plain text", "cv.docx")])
def test_registration_checks_the_resume_like_an_application(data, name):
    response = register(APIClient(), SimpleUploadedFile(name, data, "application/pdf"))
    assert response.status_code == 400 and "resume" in response.data
    assert not User.objects.filter(email="asha@new.test").exists()


@pytest.mark.django_db
def test_registration_requires_accepting_the_terms():
    response = register(
        APIClient(), SimpleUploadedFile("cv.pdf", make_pdf(RESUME), "application/pdf"), accept_terms="false"
    )
    assert response.status_code == 400 and "accept_terms" in response.data


@pytest.mark.django_db
def test_registration_parses_the_resume_and_prefills_the_profile():
    client = APIClient()
    response = register(client, SimpleUploadedFile("asha-cv.pdf", make_pdf(RESUME), "application/pdf"))
    assert response.status_code == 201, response.data
    user = User.objects.get(email="asha@new.test")
    assert user.role == Role.CANDIDATE
    profile = client.get("/api/profile").data
    assert profile["phone"] == "+91 98480 12345"
    assert profile["linkedin_url"] == "https://linkedin.com/in/asha-verma"
    assert profile["github_url"] == "https://github.com/ashav"
    assert profile["portfolio_url"] == "https://asha-portfolio.example/work"
    assert {"Python", "Django", "PostgreSQL", "React"} <= set(profile["skills"])
    assert profile["experience"][0]["title"] == "Backend Engineer"
    assert profile["experience"][0]["company"].startswith("Brightleaf")
    assert profile["education"][0]["year"] == "2022" and profile["education"][0]["score"] == "8.6"
    assert CareerProfile.objects.get(user=user).resume_filename == "asha-cv.pdf"
    assert ResumeVersion.objects.filter(user=user, is_current=True).count() == 1
    assert EmailOutbox.objects.filter(to_email=user.email, kind="registration").exists()


def test_staff_accounts_are_only_created_by_admin(users):
    for role in ("recruiter", "hr", "manager", "employee", "candidate"):
        response = as_user(users[role]).post(
            "/api/users", {"full_name": "X Y", "email": "x@corp.test", "role": "recruiter"}, format="json"
        )
        assert response.status_code == 403, role
    assert APIClient().post("/api/users", {}, format="json").status_code == 401

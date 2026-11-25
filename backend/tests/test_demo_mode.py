"""Demo mode: off by default, Try-as sign-in only when on, restricted actions for demo
accounts, upload limits, and the nightly reset (idempotent, demo data only, audited)."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient

from accounts.models import Role, User
from accounts.services import create_user
from core.demo import DEMO_UPLOAD_MAX_BYTES, reset_demo_data
from core.models import AuditLog
from core.tasks import run_nightly
from seeding.docgen import make_pdf

on = override_settings(DEMO_MODE=True)
off = override_settings(DEMO_MODE=False)


def as_user(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def demo_users(make_user):
    return {
        role: make_user(role, email=f"{email}@demo.example")
        for role, email in (
            ("candidate", "candidate"),
            ("recruiter", "recruiter"),
            ("manager", "manager"),
            ("employee", "employee"),
            ("hr", "hr"),
            ("admin", "admin"),
        )
    }


def test_demo_mode_is_off_by_default():
    from pathlib import Path

    from django.conf import settings

    source = (Path(settings.BASE_DIR) / "config" / "settings.py").read_text(encoding="utf-8")
    assert 'DEMO_MODE = env_bool("DEMO_MODE", False)' in source


@pytest.mark.django_db
@off
def test_config_and_login_when_off(demo_users):
    data = APIClient().get("/api/demo/config").data
    assert data == {"demo_mode": False, "accounts": [], "upload_limit_bytes": None}
    assert APIClient().post("/api/auth/demo-login", {"role": "candidate"}, format="json").status_code == 404


@pytest.mark.django_db
@on
def test_try_as_buttons_sign_in_to_the_seeded_accounts(demo_users):
    data = APIClient().get("/api/demo/config").data
    assert data["demo_mode"] is True and "banner" not in data  # D-87: no banner
    assert [a["role"] for a in data["accounts"]] == [
        "candidate",
        "recruiter",
        "manager",
        "employee",
        "hr",
        "admin",
    ]
    client = APIClient()
    response = client.post("/api/auth/demo-login", {"role": "hr"}, format="json")
    assert response.status_code == 200 and response.data["user"]["email"] == "hr@demo.example"
    assert "tp_access" in response.cookies
    assert AuditLog.objects.filter(action="auth.demo_login").exists()
    assert APIClient().post("/api/auth/demo-login", {"role": "superuser"}, format="json").status_code == 400


@pytest.mark.django_db
@on
def test_demo_accounts_cannot_invite_or_change_staff(demo_users, users):
    admin = as_user(demo_users["admin"])
    invite = admin.post(
        "/api/users", {"email": "x@corp.test", "full_name": "New Person", "role": "recruiter"}, format="json"
    )
    assert invite.status_code == 403 and "Demo accounts" in str(invite.data)
    assert (
        admin.patch(f"/api/users/{users['recruiter'].id}", {"is_active": False}, format="json").status_code
        == 403
    )
    # A real admin (not a demo address) is not restricted.
    real = as_user(users["admin"])
    assert (
        real.post(
            "/api/users",
            {"email": "y@corp.test", "full_name": "Real Hire", "role": "recruiter"},
            format="json",
        ).status_code
        == 201
    )


@pytest.mark.django_db
@on
def test_demo_accounts_cannot_bulk_move_or_delete(demo_users, make_job, org):
    job = make_job(owner=demo_users["recruiter"], status="draft")
    recruiter = as_user(demo_users["recruiter"])
    assert (
        recruiter.post(
            f"/api/jobs/{job.id}/applications/bulk-status",
            {"ids": ["x"], "status": "screening"},
            format="json",
        ).status_code
        == 403
    )
    assert recruiter.delete(f"/api/jobs/{job.id}").status_code == 403
    admin = as_user(demo_users["admin"])
    assert admin.delete(f"/api/departments/{org['department2'].id}").status_code == 403


@pytest.mark.django_db
@on
def test_demo_accounts_cannot_change_their_password(demo_users):
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    from notifications.models import EmailOutbox

    user = demo_users["candidate"]
    response = APIClient().post("/api/auth/password-reset", {"email": user.email}, format="json")
    assert response.status_code == 202  # same answer as for anyone
    assert not EmailOutbox.objects.filter(to_email=user.email).exists()
    confirm = APIClient().post(
        "/api/auth/password-reset/confirm",
        {
            "uid": urlsafe_base64_encode(force_bytes(user.pk)),
            "token": default_token_generator.make_token(user),
            "password": "Another-Strong-Pass-2026",
        },
        format="json",
    )
    assert confirm.status_code == 403
    user.refresh_from_db()
    assert not user.check_password("Another-Strong-Pass-2026")


@pytest.mark.django_db
@off
def test_restrictions_do_not_apply_when_demo_mode_is_off(demo_users, users):
    admin = as_user(demo_users["admin"])
    response = admin.post(
        "/api/users", {"email": "z@corp.test", "full_name": "Off Mode", "role": "recruiter"}, format="json"
    )
    assert response.status_code == 201


@pytest.mark.django_db
@on
def test_uploads_are_limited_in_demo_mode(users):
    client = as_user(users["candidate"])
    big = make_pdf(["Big", "SKILLS", "Python"] + ["x" * 120] * 4000)
    padded = big + b"%" * max(0, DEMO_UPLOAD_MAX_BYTES + 10 - len(big))
    response = client.post(
        "/api/career/profile",
        {"resume": SimpleUploadedFile("cv.pdf", padded, "application/pdf")},
        format="multipart",
    )
    assert response.status_code == 400 and "1 MB" in str(response.data)
    from files.models import StoredFile
    from files.storage import save_file

    for n in range(10):
        save_file(
            owner=users["candidate"],
            original_name=f"f{n}.pdf",
            content_type="application/pdf",
            raw=b"%PDF-1.4",
        )
    small = make_pdf(["Asha", "SKILLS", "Python"])
    response = client.post(
        "/api/career/profile",
        {"resume": SimpleUploadedFile("cv.pdf", small, "application/pdf")},
        format="multipart",
    )
    assert response.status_code == 400 and "up to 10 files" in str(response.data)
    assert StoredFile.objects.filter(owner=users["candidate"]).count() == 10


@pytest.mark.django_db
@off
def test_nightly_reset_only_runs_in_demo_mode():
    assert reset_demo_data() == {"skipped": True}
    assert run_nightly()["tasks"]["demo_reset"] is False


@pytest.mark.django_db(transaction=True, serialized_rollback=True)
@on
def test_nightly_reset_is_idempotent_and_keeps_real_accounts():
    from django.core.management import call_command

    real = create_user(
        email="real.person@company.test",
        full_name="Real Person",
        role=Role.CANDIDATE,
        password="Correct-Horse-42!",
    )
    call_command("seed")
    first = run_nightly()
    assert first["tasks"]["demo_reset"] is True
    counts = (User.objects.filter(email__endswith=".example").count(), User.objects.count())
    run_nightly()
    assert (User.objects.filter(email__endswith=".example").count(), User.objects.count()) == counts
    assert User.objects.filter(pk=real.pk).exists()
    assert AuditLog.objects.filter(action="demo.reset").count() == 2
    assert User.objects.filter(email="candidate@demo.example", role=Role.CANDIDATE).exists()


@pytest.mark.django_db
@on
def test_nightly_hook_answers_at_once_and_resets_in_the_background():
    from unittest import mock

    from rest_framework.test import APIClient

    from core import demo

    started = []

    class InlineThread:
        def __init__(self, target, **kwargs):
            self.target = target

        def start(self):
            started.append(True)
            self.target()

    with (
        mock.patch.object(demo, "reset_demo_data", return_value={"skipped": False}) as reset,
        mock.patch("threading.Thread", InlineThread),
    ):
        response = APIClient().post(
            "/api/internal/nightly", HTTP_X_TICK_SECRET="test-internal-secret-0123456789"
        )
    assert response.status_code == 200 and response.data["tasks"]["demo_reset"] == "started"
    assert started == [True] and reset.call_count == 1


@pytest.mark.django_db
@on
def test_a_second_reset_never_overlaps_a_running_one():
    from core import demo

    assert demo._reset_lock.acquire(blocking=False)
    try:
        assert demo.start_demo_reset_in_background() == "running"
    finally:
        demo._reset_lock.release()

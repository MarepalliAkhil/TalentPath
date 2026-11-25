"""Prompt 1, part G: email delivery (D-86). Providers, templates, the outbox and bell,
allowlist, rate limits, retries with backoff, and no credentials in logs or stored errors."""

import logging
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from unittest import mock

import pytest
from django.utils import timezone

from notifications import delivery
from notifications.models import EmailOutbox, EmailStatus, Notification
from notifications.services import notify, queue_email
from notifications.templates import TEMPLATES, render

SECRET = "abcd efgh ijkl mnop"  # looks like a Gmail App Password
API_KEY = "xkeysib-0123456789abcdef0123456789abcdef"
BACKEND = Path(__file__).resolve().parents[1]
REAL = dict(
    EMAIL_PROVIDER="smtp",
    EMAIL_HOST_USER="sender@gmail.test",
    EMAIL_HOST_PASSWORD=SECRET,
    EMAIL_API_KEY=API_KEY,
    EMAIL_MAX_PER_RECIPIENT_PER_HOUR=2,
    EMAIL_MAX_PER_HOUR=3,
    EMAIL_DAILY_CAP=4,
    EMAIL_ALLOWLIST="",
)


def write(to="person@mailbox.in", kind="application_status", **extra):
    return queue_email(
        to_email=to,
        subject="Your application moved",
        body="Hi,\n\nGood news.\n\nhttps://careers.test/candidate",
        kind=kind,
        **extra,
    )


def test_operation_emails_have_branded_html_and_plain_text():
    for kind in (
        "registration",
        "application_received",
        "application_status",
        "assignment_link",
        "interview_link",
        "hr_round_link",
        "offer_sent",
        "onboarding_request",
        "onboarding_complete",
        "leave_decided",
        "payslip_ready",
    ):
        assert kind in TEMPLATES, kind
    plain, html = render(
        kind="offer_sent",
        subject="Your offer <3",
        body="Hi Asha,\n\nYour offer is ready.\n\nhttps://careers.test/offers/1",
    )
    assert "Read your offer: https://careers.test/offers/1" in plain
    assert (
        "<!doctype html>" in html
        and "Your offer &lt;3" in html
        and 'href="https://careers.test/offers/1"' in html
    )
    assert "TalentPath" in html and "Change which emails you get" in plain


def test_every_email_is_in_the_outbox_and_the_bell(users, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        email = write(to=users["candidate"].email, user=users["candidate"])
    email.refresh_from_db()
    assert email.status == EmailStatus.SENT and email.provider == "console" and email.html_body
    assert Notification.objects.filter(user=users["candidate"], title="Your application moved").exists()
    with django_capture_on_commit_callbacks(execute=True):
        notify(users["candidate"], kind="offer_sent", title="Offer ready", body="Open it.", link="/offers")
    assert Notification.objects.filter(user=users["candidate"], title="Offer ready").count() == 1  # not twice
    assert EmailOutbox.objects.filter(kind="offer_sent", status=EmailStatus.SENT).count() == 1


def test_console_logs_masked_recipient_and_never_the_body(users, caplog, django_capture_on_commit_callbacks):
    caplog.set_level(logging.INFO, logger="talentpath.email")
    with django_capture_on_commit_callbacks(execute=True):
        queue_email(
            to_email="asha.verma@mailbox.in",
            subject="Reset",
            body="Secret link https://x.test/reset?token=abc",
            kind="password_reset",
        )
    text = caplog.text
    assert "a***@mailbox.in" in text and "asha.verma" not in text and "token=abc" not in text


@pytest.mark.django_db
def test_settings_refuse_a_real_provider_without_credentials():
    def run(extra):
        env = {k: v for k, v in os.environ.items() if not k.startswith("EMAIL_")}
        env.update({"DJANGO_LOAD_DOTENV": "0", "DJANGO_SETTINGS_MODULE": "config.settings", **extra})
        return subprocess.run(  # noqa: S603 - fixed argv: this Python importing the settings
            [sys.executable, "-c", "import config.settings as s; print(s.EMAIL_PROVIDER)"],
            cwd=BACKEND,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )

    from django.conf import settings as live

    base = {
        "SECRET_KEY": live.SECRET_KEY,
        "DATABASE_URL": os.environ.get("DATABASE_URL", "postgres://u:p@localhost:5432/db"),
        "FIELD_ENCRYPTION_KEY": os.environ["FIELD_ENCRYPTION_KEY"],
        "BLIND_INDEX_KEY": os.environ["BLIND_INDEX_KEY"],
        "INTERNAL_TICK_SECRET": os.environ["INTERNAL_TICK_SECRET"],
    }
    assert "EMAIL_PROVIDER=smtp needs" in run({**base, "EMAIL_PROVIDER": "smtp"}).stderr
    assert (
        "EMAIL_PROVIDER=api needs"
        in run({**base, "EMAIL_PROVIDER": "api", "EMAIL_API_PROVIDER": "brevo"}).stderr
    )
    assert "must be console, smtp or api" in run({**base, "EMAIL_PROVIDER": "pigeon"}).stderr
    ok = run(
        {**base, "EMAIL_PROVIDER": "smtp", "EMAIL_HOST_USER": "a@gmail.test", "EMAIL_HOST_PASSWORD": SECRET}
    )
    assert ok.returncode == 0 and ok.stdout.strip() == "smtp", ok.stderr
    assert SECRET not in ok.stdout + ok.stderr


def test_no_credentials_in_code_or_example_files():
    root = BACKEND.parent
    for path in [root / "backend" / ".env.example", root / "render.yaml", BACKEND / "config" / "settings.py"]:
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith(("EMAIL_HOST_PASSWORD=", "EMAIL_API_KEY=")):
                assert line.split("=", 1)[1].strip() == "", line


def test_smtp_provider_sends_and_marks_sent(db, settings):
    for key, value in REAL.items():
        setattr(settings, key, value)
    email = write()
    with mock.patch.object(delivery, "send_smtp") as send:
        assert delivery.deliver(email.pk) == EmailStatus.SENT
    send.assert_called_once()
    email.refresh_from_db()
    assert email.provider == "smtp" and email.attempts == 1 and email.sent_at is not None


def test_api_provider_builds_a_brevo_request_with_the_key_in_a_header(db, settings):
    for key, value in {**REAL, "EMAIL_PROVIDER": "api", "EMAIL_API_PROVIDER": "brevo"}.items():
        setattr(settings, key, value)
    email = write()
    captured = {}

    class Response:
        status = 201

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout):
        captured["url"], captured["headers"], captured["body"] = (
            request.full_url,
            dict(request.headers),
            request.data,
        )
        return Response()

    with mock.patch("urllib.request.urlopen", fake_urlopen):
        assert delivery.deliver(email.pk) == EmailStatus.SENT
    assert captured["url"] == "https://api.brevo.com/v3/smtp/email"
    assert captured["headers"]["Api-key"] == API_KEY
    assert API_KEY.encode() not in captured["body"] and b"htmlContent" in captured["body"]


def test_reserved_demo_addresses_are_never_sent(db, settings):
    for key, value in REAL.items():
        setattr(settings, key, value)
    email = write(to="candidate@demo.example")
    with mock.patch.object(delivery, "send_smtp") as send:
        assert delivery.deliver(email.pk) == EmailStatus.HELD
    send.assert_not_called()
    email.refresh_from_db()
    assert email.hold_reason == "Reserved demo address: never sent"


def test_allowlist_keeps_other_addresses_in_the_outbox(db, settings):
    for key, value in {**REAL, "EMAIL_ALLOWLIST": "me@mailbox.in, @team.in"}.items():
        setattr(settings, key, value)
    with mock.patch.object(delivery, "send_smtp") as send:
        assert delivery.deliver(write(to="Me@Mailbox.in").pk) == EmailStatus.SENT
        assert delivery.deliver(write(to="anyone@team.in").pk) == EmailStatus.SENT
        held = write(to="stranger@mailbox.in")
        assert delivery.deliver(held.pk) == EmailStatus.HELD
    assert send.call_count == 2
    held.refresh_from_db()
    assert held.hold_reason == "Not on EMAIL_ALLOWLIST" and held.status == EmailStatus.HELD


def test_rate_limits_per_recipient_per_hour_and_per_day(db, settings):
    for key, value in REAL.items():
        setattr(settings, key, value)
    with mock.patch.object(delivery, "send_smtp"):
        results = [delivery.deliver(write(to="same@mailbox.in").pk) for _ in range(3)]
        assert results == [EmailStatus.SENT, EmailStatus.SENT, EmailStatus.HELD]
        assert (
            EmailOutbox.objects.filter(hold_reason="Limit reached for this recipient this hour").count() == 1
        )
        assert delivery.deliver(write(to="other@mailbox.in").pk) == EmailStatus.SENT  # 3 sent this hour
        assert delivery.deliver(write(to="third@mailbox.in").pk) == EmailStatus.HELD
        assert EmailOutbox.objects.filter(hold_reason="Hourly email limit reached").exists()
        EmailOutbox.objects.filter(status=EmailStatus.SENT).update(
            sent_at=timezone.now() - timedelta(hours=2)
        )
        assert delivery.deliver(write(to="fourth@mailbox.in").pk) == EmailStatus.SENT  # 4 today: cap reached
        assert delivery.deliver(write(to="fifth@mailbox.in").pk) == EmailStatus.HELD
        assert EmailOutbox.objects.filter(hold_reason="Daily email cap reached").exists()


def test_failures_retry_with_backoff_then_give_up_and_never_store_secrets(db, settings):
    for key, value in {**REAL, "EMAIL_MAX_ATTEMPTS": 3}.items():
        setattr(settings, key, value)
    email = write()
    boom = RuntimeError(f"535 auth failed for sender@gmail.test password={SECRET} api-key {API_KEY}")
    with mock.patch.object(delivery, "send_smtp", side_effect=boom):
        assert delivery.deliver(email.pk) == EmailStatus.QUEUED
        email.refresh_from_db()
        assert email.attempts == 1 and email.next_attempt_at > timezone.now() + timedelta(seconds=50)
        assert (
            SECRET not in email.last_error and API_KEY not in email.last_error and "535" in email.last_error
        )
        assert delivery.retry_due() == 0  # not due yet
        later = timezone.now() + timedelta(minutes=2)
        assert delivery.retry_due(later) == 1
        email.refresh_from_db()
        assert email.attempts == 2 and email.next_attempt_at >= later + timedelta(minutes=4)
        delivery.retry_due(timezone.now() + timedelta(hours=2))
    email.refresh_from_db()
    assert email.status == EmailStatus.FAILED and email.attempts == 3


def test_tick_retries_due_emails(db, settings, client_for):
    from rest_framework.test import APIClient

    for key, value in REAL.items():
        setattr(settings, key, value)
    email = write()
    EmailOutbox.objects.filter(pk=email.pk).update(next_attempt_at=timezone.now() - timedelta(minutes=1))
    with mock.patch.object(delivery, "send_smtp"):
        response = APIClient().post(
            "/api/internal/tick", HTTP_X_TICK_SECRET="test-internal-secret-0123456789"
        )
    assert response.status_code == 200 and response.data["tasks"]["emails_retried"] == 1
    email.refresh_from_db()
    assert email.status == EmailStatus.SENT


def test_admin_email_log_shows_delivery_status(users, client_for, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        write(to=users["candidate"].email, user=users["candidate"])
    data = client_for("admin").get("/api/outbox").data
    assert data["provider"] == "console" and data["counts"]["sent"] >= 1
    row = data["results"][0]
    assert row["status"] == "sent" and row["provider"] == "console" and "last_error" in row
    assert client_for("hr").get("/api/outbox").status_code == 403

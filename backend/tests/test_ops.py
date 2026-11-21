import os
import subprocess
import sys
from pathlib import Path

from rest_framework.test import APIClient

from notifications.models import EmailOutbox
from notifications.services import issue_ws_ticket, redeem_ws_ticket

BACKEND = Path(__file__).resolve().parent.parent
SECRET = "test-internal-secret-0123456789"


def test_ping_makes_zero_queries(db, django_assert_num_queries):
    with django_assert_num_queries(0):
        resp = APIClient().get("/api/ping")
    assert resp.status_code == 200 and resp.data == {"status": "ok"}
    assert resp["Cache-Control"] == "no-store"


def test_cron_endpoints_need_the_secret_header(db, users):
    client = APIClient()
    for path in ("/api/internal/tick", "/api/internal/nightly"):
        assert client.post(path).status_code == 403
        assert client.post(path, HTTP_X_INTERNAL_SECRET="wrong").status_code == 403
        ok = client.post(path, HTTP_X_INTERNAL_SECRET=SECRET)
        assert ok.status_code == 200 and "ran_at" in ok.data
    signed_in = APIClient()
    signed_in.force_authenticate(users["hr_admin"])
    assert signed_in.post("/api/internal/tick").status_code == 403


def test_websocket_tickets_are_single_use(users, client_for):
    resp = client_for("employee").post("/api/realtime/ticket")
    assert resp.status_code == 200 and resp.data["expires_in"] == 30
    ticket = resp.data["ticket"]
    assert redeem_ws_ticket(ticket) == str(users["employee"].id)
    assert redeem_ws_ticket(ticket) is None
    assert redeem_ws_ticket("") is None
    assert redeem_ws_ticket(issue_ws_ticket(users["candidate"])) == str(users["candidate"].id)


def test_demo_inbox(users, settings):
    APIClient().post("/api/auth/password-reset", {"email": users["candidate"].email}, format="json")
    client = APIClient()
    resp = client.get(f"/api/demo/inbox?email={users['candidate'].email}")
    assert resp.status_code == 200 and len(resp.data["results"]) == 1
    assert client.get("/api/demo/inbox?email=someone@gmail.com").status_code == 404
    settings.DEMO_MODE = False
    assert client.get(f"/api/demo/inbox?email={users['candidate'].email}").status_code == 404
    assert EmailOutbox.objects.count() == 1


def _import_settings_with(env_overrides, drop=()):
    env = {k: v for k, v in os.environ.items() if k not in drop}
    env.update({"DJANGO_LOAD_DOTENV": "0", **env_overrides})
    return subprocess.run(
        [sys.executable, "-c", "import config.settings"],
        cwd=BACKEND,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_settings_refuse_to_start_without_required_env():
    result = _import_settings_with({}, drop=("SECRET_KEY", "FIELD_ENCRYPTION_KEY"))
    assert result.returncode != 0
    assert "Missing required environment variables" in result.stderr
    assert "SECRET_KEY" in result.stderr and "FIELD_ENCRYPTION_KEY" in result.stderr


def test_settings_refuse_weak_keys():
    short = _import_settings_with({"SECRET_KEY": "too-short"})
    assert short.returncode != 0 and "SECRET_KEY" in short.stderr
    bad_key = _import_settings_with({"FIELD_ENCRYPTION_KEY": "c2hvcnQ="})
    assert bad_key.returncode != 0 and "32 bytes" in bad_key.stderr


def test_in_memory_channel_layer_without_redis(settings):
    assert settings.CHANNEL_LAYERS["default"]["BACKEND"] == "channels.layers.InMemoryChannelLayer"

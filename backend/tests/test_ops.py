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


def test_cron_endpoints_need_the_secret_header(db, users, monkeypatch):
    # Test settings run with DEMO_MODE on: never start a real background reseed here.
    monkeypatch.setattr("core.demo.start_demo_reset_in_background", lambda: "started")
    client = APIClient()
    for path in ("/api/internal/tick", "/api/internal/nightly"):
        assert client.post(path).status_code == 403
        # The old header name is no longer accepted.
        assert client.post(path, HTTP_X_INTERNAL_SECRET=SECRET).status_code == 403
        assert client.post(path, HTTP_X_TICK_SECRET=SECRET[:-1]).status_code == 403
        assert client.post(path, HTTP_X_TICK_SECRET="wrong").status_code == 403
        ok = client.post(path, HTTP_X_TICK_SECRET=SECRET)
        assert ok.status_code == 200 and "ran_at" in ok.data
    signed_in = APIClient()
    signed_in.force_authenticate(users["hr"])
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
    return subprocess.run(  # noqa: S603 - fixed argv: this Python running a test snippet
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


# ---------------------------------------------------------------- production (week 4B)
PROD_ENV = {
    "PRODUCTION": "true",
    "DEBUG": "false",
    "FRONTEND_DOMAIN": "talentpath.vercel.app",
    "RENDER_EXTERNAL_HOSTNAME": "talentpath-api.onrender.com",
    "SECRET_KEY": "prod-sample-" + "k7Qz9vX2mP4wR8tY1uE6oI3aS5dF0gH" * 2,
    "DATABASE_URL": "postgres://user:pass@ep-sample-123.ap-southeast-1.aws.neon.tech/neondb",
    "INTERNAL_TICK_SECRET": "sample-tick-secret-0123456789abcdef",
    "ALLOWED_HOSTS": "",
    "SITE_URL": "",
    "CSRF_TRUSTED_ORIGINS": "",
    "WS_ALLOWED_ORIGINS": "",
}


def _run_production(code: str, overrides=None, drop=()):
    env = {k: v for k, v in os.environ.items() if k not in drop}
    env.update(
        {
            "DJANGO_LOAD_DOTENV": "0",
            "DJANGO_SETTINGS_MODULE": "config.settings",
            **PROD_ENV,
            **(overrides or {}),
        }
    )
    for name in drop:
        env.pop(name, None)
    return subprocess.run(  # noqa: S603 - fixed argv: this Python running a test snippet
        [sys.executable, "-c", code], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=120
    )


def test_production_refuses_to_start_without_its_variables():
    result = _run_production("import config.settings", drop=("FRONTEND_DOMAIN",))
    assert result.returncode != 0 and "FRONTEND_DOMAIN" in result.stderr
    debug = _run_production("import config.settings", {"DEBUG": "true"})
    assert debug.returncode != 0 and "DEBUG must be off" in debug.stderr


def test_production_hosts_origins_cookies_and_tls():
    code = (
        "import json, config.settings as s;"
        "print(json.dumps({'hosts': s.ALLOWED_HOSTS, 'csrf': s.CSRF_TRUSTED_ORIGINS,"
        "'ws': s.WS_ALLOWED_ORIGINS,"
        "'site': s.SITE_URL, 'ssl': s.DATABASES['default']['OPTIONS'].get('sslmode'),"
        "'age': s.DATABASES['default']['CONN_MAX_AGE'], 'secure': s.COOKIE_SECURE,"
        "'csrf_secure': s.CSRF_COOKIE_SECURE,"
        "'redirect': s.SECURE_SSL_REDIRECT, 'hsts': s.SECURE_HSTS_SECONDS, 'debug': s.DEBUG,"
        "'proxy': list(s.SECURE_PROXY_SSL_HEADER), 'layer': s.CHANNEL_LAYERS['default']['BACKEND'],"
        "'cache': s.CACHES['default']['BACKEND']}))"
    )
    result = _run_production(code)
    assert result.returncode == 0, result.stderr
    import json

    data = json.loads(result.stdout.strip().splitlines()[-1])
    assert data["hosts"] == ["talentpath-api.onrender.com", "talentpath.vercel.app"]
    assert data["csrf"] == ["https://talentpath.vercel.app"] and data["ws"] == [
        "https://talentpath.vercel.app"
    ]
    assert data["site"] == "https://talentpath.vercel.app"
    assert data["ssl"] == "require" and data["age"] == 0
    assert data["secure"] and data["csrf_secure"] and data["redirect"] and data["hsts"] >= 31536000
    assert data["debug"] is False
    assert data["proxy"] == ["HTTP_X_FORWARDED_PROTO", "https"]
    assert data["layer"].endswith("InMemoryChannelLayer") and data["cache"].endswith("LocMemCache")


def test_production_passes_the_deploy_checks():
    pytest = __import__("pytest")
    pytest.importorskip("psycopg")
    result = _run_production(
        "import django, sys; django.setup(); from django.core.management import call_command;"
        "call_command('check', deploy=True, fail_level='WARNING')"
    )
    assert result.returncode == 0, result.stderr + result.stdout


def test_local_settings_are_unchanged_without_production(settings):
    assert settings.PRODUCTION is False
    assert settings.SECURE_SSL_REDIRECT is False


def test_tick_is_cheap_when_nothing_is_due(db, django_assert_max_num_queries):
    from core.tasks import run_tick

    with django_assert_max_num_queries(20):
        result = run_tick()
    assert all(not v for v in result["tasks"].values())


def test_health_check_works_whatever_host_the_platform_sends(db, settings, django_assert_num_queries):
    settings.ALLOWED_HOSTS = ["talentpath-api.onrender.com"]
    with django_assert_num_queries(0):
        ping = APIClient().get("/api/ping", HTTP_HOST="localhost:10000")
    assert ping.status_code == 200 and ping.json() == {"status": "ok"}
    # Only the health check is exempt: any other path with a bad host is still refused.
    assert APIClient().get("/api/public/jobs", HTTP_HOST="localhost:10000").status_code == 400
    assert APIClient().get("/api/ping", HTTP_HOST="talentpath-api.onrender.com").status_code == 200

import re

import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

from accounts.models import Role, User
from core.models import AuditLog
from notifications.models import EmailOutbox

from .conftest import PASSWORD, ROLES

DASHBOARDS = {
    "candidate": "/candidate",
    "recruiter": "/recruiter",
    "hiring_manager": "/manager",
    "employee": "/employee",
    "hr_admin": "/admin",
}


def login(client, email, password=PASSWORD):
    return client.post("/api/auth/login", {"email": email, "password": password}, format="json")


@pytest.mark.django_db
def test_candidate_registration_signs_in_with_httponly_cookies():
    client = APIClient()
    resp = client.post(
        "/api/auth/register",
        {"full_name": "Asha Verma", "email": "Asha@Example.test", "password": "Sturdy-Pass-123"},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.data["user"]["role"] == Role.CANDIDATE
    assert resp.data["user"]["dashboard"] == "/candidate"
    access = resp.cookies["tp_access"]
    assert access["httponly"] and access["samesite"] == "Lax"
    assert resp.cookies["tp_refresh"]["httponly"]
    assert resp.cookies["tp_refresh"]["path"] == "/api/auth"
    user = User.objects.get(email="asha@example.test")
    assert user.check_password("Sturdy-Pass-123")
    assert user.password != "Sturdy-Pass-123"
    assert hasattr(user, "profile")
    me = client.get("/api/auth/me")
    assert me.status_code == 200 and me.data["user"]["email"] == "asha@example.test"


@pytest.mark.django_db
def test_registration_rejects_duplicates_and_weak_passwords(make_user):
    make_user(email="taken@test.example")
    client = APIClient()
    dup = client.post(
        "/api/auth/register",
        {"full_name": "X Y", "email": "TAKEN@test.example", "password": "Sturdy-Pass-123"},
        format="json",
    )
    assert dup.status_code == 400 and "email" in dup.data
    weak = client.post(
        "/api/auth/register",
        {"full_name": "X Y", "email": "new@test.example", "password": "password"},
        format="json",
    )
    assert weak.status_code == 400


@pytest.mark.django_db
def test_registration_cannot_choose_a_role():
    resp = APIClient().post(
        "/api/auth/register",
        {"full_name": "Sneaky", "email": "s@test.example", "password": "Sturdy-Pass-123", "role": "hr_admin"},
        format="json",
    )
    assert resp.status_code == 201
    assert User.objects.get(email="s@test.example").role == Role.CANDIDATE


@pytest.mark.parametrize("role", ROLES)
def test_login_redirects_each_role_to_its_dashboard(role, users):
    resp = login(APIClient(), users[role].email)
    assert resp.status_code == 200
    assert resp.data["user"]["dashboard"] == DASHBOARDS[role]
    assert AuditLog.objects.filter(action="auth.login", actor=users[role]).exists()


def test_login_failures(users):
    client = APIClient()
    assert login(client, users["candidate"].email, "wrong-password").status_code == 401
    users["employee"].is_active = False
    users["employee"].save()
    assert login(client, users["employee"].email).status_code == 401
    assert login(client, "nobody@test.example").status_code == 401
    assert AuditLog.objects.filter(action="auth.login_failed").count() == 3


def test_logout_clears_cookies_and_blacklists_refresh(users):
    client = APIClient()
    assert login(client, users["recruiter"].email).status_code == 200
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 204
    assert resp.cookies["tp_access"].value == ""
    assert BlacklistedToken.objects.count() == 1
    assert client.get("/api/auth/me").status_code == 401


def test_refresh_rotates_and_old_refresh_is_rejected(users):
    client = APIClient()
    login(client, users["candidate"].email)
    old = client.cookies["tp_refresh"].value
    resp = client.post("/api/auth/refresh")
    assert resp.status_code == 200
    assert client.cookies["tp_refresh"].value != old
    client.cookies["tp_refresh"] = old
    assert client.post("/api/auth/refresh").status_code == 401


def test_expired_or_garbage_access_cookie_is_anonymous(users):
    client = APIClient()
    client.cookies["tp_access"] = "not-a-jwt"
    assert client.get("/api/auth/me").status_code == 401


def test_csrf_is_enforced_on_unsafe_methods(users):
    client = APIClient(enforce_csrf_checks=True)
    blocked = login(client, users["candidate"].email)
    assert blocked.status_code == 403
    client.get("/api/auth/csrf")
    token = client.cookies["csrftoken"].value
    ok = client.post(
        "/api/auth/login",
        {"email": users["candidate"].email, "password": PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert ok.status_code == 200
    # Signed in with a cookie, a write without the header is still refused.
    assert client.patch("/api/profile", {"headline": "x"}, format="json").status_code == 403
    assert (
        client.patch("/api/profile", {"headline": "x"}, format="json", HTTP_X_CSRFTOKEN=token).status_code
        == 200
    )


def test_password_reset_flow(users):
    client = APIClient()
    user = users["candidate"]
    resp = client.post("/api/auth/password-reset", {"email": user.email.upper()}, format="json")
    assert resp.status_code == 202
    mail = EmailOutbox.objects.get(to_email=user.email, kind="password_reset")
    uid, token = re.search(r"uid=([^&\s]+)&token=(\S+)", mail.body).groups()
    bad = client.post(
        "/api/auth/password-reset/confirm",
        {"uid": uid, "token": "wrong-token", "password": "Brand-New-Pass-77"},
        format="json",
    )
    assert bad.status_code == 400
    ok = client.post(
        "/api/auth/password-reset/confirm",
        {"uid": uid, "token": token, "password": "Brand-New-Pass-77"},
        format="json",
    )
    assert ok.status_code == 200
    assert login(client, user.email, "Brand-New-Pass-77").status_code == 200
    reused = client.post(
        "/api/auth/password-reset/confirm",
        {"uid": uid, "token": token, "password": "Another-Pass-88"},
        format="json",
    )
    assert reused.status_code == 400


def test_password_reset_does_not_reveal_unknown_emails(db):
    resp = APIClient().post("/api/auth/password-reset", {"email": "ghost@test.example"}, format="json")
    assert resp.status_code == 202
    assert EmailOutbox.objects.count() == 0


def test_login_rate_limit_per_ip(db):
    client = APIClient()
    codes = [login(client, f"user{i}@test.example", "x").status_code for i in range(11)]
    assert codes[:10] == [401] * 10
    assert codes[10] == 429


def test_login_lockout_per_account(users):
    client = APIClient()
    email = users["recruiter"].email
    for _ in range(5):
        assert login(client, email, "wrong").status_code == 401
    assert login(client, email).status_code == 429  # even the right password waits


def test_upload_endpoint_is_rate_limited(client_for):
    client = client_for("candidate")
    codes = [client.post("/api/applications", {}, format="json").status_code for _ in range(21)]
    assert set(codes[:20]) == {400}
    assert codes[20] == 429


def test_production_hasher_is_argon2():
    import config.settings as production

    assert production.PASSWORD_HASHERS[0].endswith("Argon2PasswordHasher")

from django.db import connection

from accounts.models import Role, User
from core.crypto import blind_index
from core.models import AuditLog
from notifications.models import EmailOutbox

from .conftest import PASSWORD


def test_admin_creates_staff_with_invite(client_for):
    resp = client_for("admin").post(
        "/api/users",
        {"full_name": "New Recruiter", "email": "New.Rec@test.example", "role": "recruiter"},
        format="json",
    )
    assert resp.status_code == 201
    user = User.objects.get(email="new.rec@test.example")
    assert user.role == Role.RECRUITER
    assert not user.has_usable_password()
    mail = EmailOutbox.objects.get(to_email=user.email)
    assert mail.kind == "staff_invite" and "/reset-password?uid=" in mail.body
    assert AuditLog.objects.filter(action="users.create", target_id=str(user.id)).exists()


def test_staff_endpoint_cannot_create_candidates(client_for):
    resp = client_for("admin").post(
        "/api/users", {"full_name": "X Y", "email": "c@test.example", "role": "candidate"}, format="json"
    )
    assert resp.status_code == 400


def test_admin_cannot_lock_themselves_out(users, client_for):
    admin = users["admin"]
    client = client_for("admin")
    assert client.patch(f"/api/users/{admin.id}", {"is_active": False}, format="json").status_code == 400
    assert client.patch(f"/api/users/{admin.id}", {"role": "employee"}, format="json").status_code == 400


def test_deactivated_user_cannot_sign_in(users, client_for):
    from rest_framework.test import APIClient

    target = users["employee"]
    resp = client_for("admin").patch(f"/api/users/{target.id}", {"is_active": False}, format="json")
    assert resp.status_code == 200 and resp.data["is_active"] is False
    login = APIClient().post("/api/auth/login", {"email": target.email, "password": PASSWORD}, format="json")
    assert login.status_code == 401


def test_profile_personal_data_is_encrypted_with_blind_index(users, client_for):
    client = client_for("candidate")
    resp = client.patch(
        "/api/profile",
        {"phone": "+91 98765 43210", "address": "12 Lake Road, Vijayawada", "headline": "Backend dev"},
        format="json",
    )
    assert resp.status_code == 200
    assert resp.data["phone"] == "+91 98765 43210"
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT phone, address, phone_bidx FROM accounts_profile WHERE user_id = %s",
            [users["candidate"].id],
        )
        phone, address, bidx = cursor.fetchone()
    assert phone.startswith("v1:") and "98765" not in phone
    assert address.startswith("v1:") and "Lake" not in address
    assert bidx == blind_index("+919876543210", "phone")
    profile = users["candidate"].profile
    profile.refresh_from_db()
    assert profile.address == "12 Lake Road, Vijayawada"
    assert client.get("/api/profile").data["address"] == "12 Lake Road, Vijayawada"


def test_profile_rejects_bad_phone(client_for):
    resp = client_for("employee").patch("/api/profile", {"phone": "call me maybe"}, format="json")
    assert resp.status_code == 400

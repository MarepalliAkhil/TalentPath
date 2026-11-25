"""Prompt 1, part A: six roles, the role migration, admin user management (D-80, D-81)."""

import importlib

import pytest
from django.apps import apps as django_apps
from rest_framework.test import APIClient

from accounts.models import Profile, Role, User
from core.models import AuditLog
from core.policy import ROLES, allowed_principals, load_policy
from hr.models import Employee

from .conftest import PASSWORD

six_roles = importlib.import_module("accounts.migrations.0002_six_roles")
offer_steps = importlib.import_module("offers.migrations.0002_approval_steps")


def as_user(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_there_are_six_roles_with_their_own_dashboards():
    assert ROLES == ("candidate", "recruiter", "manager", "employee", "hr", "admin")
    assert load_policy()["dashboards"] == {
        "candidate": "/candidate",
        "recruiter": "/recruiter",
        "manager": "/manager",
        "employee": "/employee",
        "hr": "/hr",
        "admin": "/admin",
    }


@pytest.mark.parametrize(
    "action,allowed",
    [
        # admin: accounts and organisation only
        ("users.create", {"admin"}),
        ("org.manage", {"admin"}),
        ("audit.list", {"admin"}),
        ("outbox.list", {"admin"}),
        # hr: HR round, offers, onboarding, HR settings
        ("offers.approve", {"manager", "hr"}),
        ("onboarding.hire", {"recruiter", "hr"}),
        ("hr.config", {"hr"}),
        # recruiter owns jobs and the pipeline
        ("jobs.create", {"recruiter", "hr"}),
        ("applications.status", {"recruiter", "hr"}),
        # manager: own team
        ("leave.approve", {"recruiter", "manager", "employee", "hr"}),
        # candidate
        ("applications.create", {"candidate"}),
    ],
)
def test_each_role_has_exactly_its_actions(action, allowed):
    assert allowed_principals(action) == frozenset(allowed)


def test_admin_cannot_reach_candidates_documents_or_applications(users, application):
    admin = as_user(users["admin"])
    assert admin.get(f"/api/applications/{application.id}/resume").status_code == 403
    assert admin.get(f"/api/applications/{application.id}").status_code == 403
    assert admin.get(f"/api/jobs/{application.job_id}/applications").status_code == 403
    for action, roles in load_policy()["actions"].items():
        if action.startswith(("applications.", "offers.", "interviews.", "career.")):
            assert "admin" not in roles, action


@pytest.mark.django_db
def test_role_migration_moves_every_user_and_reverses():
    make = User.objects.create_user
    old = {
        "admin@demo.example": "hr_admin",
        "people@corp.test": "hr_admin",
        "hm@corp.test": "hiring_manager",
        "rec@corp.test": "recruiter",
        "cand@corp.test": "candidate",
    }
    for email, role in old.items():
        user = make(email=email, full_name=email, password=PASSWORD)
        User.objects.filter(pk=user.pk).update(role=role)
    six_roles.forwards(django_apps, None)
    roles = dict(User.objects.values_list("email", "role"))
    assert roles == {
        "admin@demo.example": "admin",
        "people@corp.test": "hr",
        "hm@corp.test": "manager",
        "rec@corp.test": "recruiter",
        "cand@corp.test": "candidate",
    }
    six_roles.backwards(django_apps, None)
    assert dict(User.objects.values_list("email", "role")) == old
    assert User.objects.count() == len(old)  # nothing lost either way


def test_offer_approval_step_migration(users, application):
    from offers.models import Offer

    offer = Offer(application=application, expires_on="2030-01-01", created_by=users["recruiter"])
    offer.data = {"designation": "Engineer"}
    offer.save()
    Offer.objects.filter(pk=offer.pk).update(approval_step="hiring_manager")
    offer_steps.forwards(django_apps, None)
    assert Offer.objects.get(pk=offer.pk).approval_step == "manager"
    offer_steps.backwards(django_apps, None)
    assert Offer.objects.get(pk=offer.pk).approval_step == "hiring_manager"


# ---------------------------------------------------------------- admin user management
def test_admin_creates_staff_with_an_employee_record_and_invite(users, team, org):
    from notifications.models import EmailOutbox

    response = as_user(users["admin"]).post(
        "/api/users",
        {
            "full_name": "Nisha Gupta",
            "email": "nisha@corp.test",
            "role": "manager",
            "employee": {
                "department": str(org["department"].id),
                "location": str(org["location"].id),
                "designation": "Engineering Manager",
                "joined_on": "2026-12-01",
                "manager": str(team["boss"].id),
            },
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    user = User.objects.get(email="nisha@corp.test")
    assert user.role == Role.MANAGER and not user.has_usable_password()
    assert user.employee.manager == team["boss"] and user.employee.code.startswith("LW")
    assert EmailOutbox.objects.filter(to_email="nisha@corp.test", kind="staff_invite").exists()
    assert AuditLog.objects.filter(action="users.create", target_id=str(user.id)).exists()


@pytest.mark.parametrize("role", ["candidate", "admin", "hr_admin", "hiring_manager"])
def test_admin_can_only_give_staff_roles(users, role):
    response = as_user(users["admin"]).post(
        "/api/users", {"full_name": "X Person", "email": "x@corp.test", "role": role}, format="json"
    )
    assert response.status_code == 400


def test_admin_assigns_roles_with_a_reason_and_it_is_audited(users):
    admin = as_user(users["admin"])
    target = users["recruiter"]
    no_reason = admin.patch(f"/api/users/{target.id}", {"role": "hr"}, format="json")
    assert no_reason.status_code == 400 and "reason" in no_reason.data
    done = admin.patch(
        f"/api/users/{target.id}", {"role": "hr", "reason": "Moved to the HR team in December"}, format="json"
    )
    assert done.status_code == 200 and done.data["role"] == "hr"
    log = AuditLog.objects.get(action="users.override", target_id=str(target.id))
    assert log.meta["fields"] == ["role"] and log.meta["reason"] == "Moved to the HR team in December"


def test_admin_cannot_turn_people_into_admins_or_candidates_into_staff(users):
    admin = as_user(users["admin"])
    reason = {"reason": "Testing the guard rails here"}
    assert (
        admin.patch(
            f"/api/users/{users['recruiter'].id}", {"role": "admin", **reason}, format="json"
        ).status_code
        == 400
    )
    assert (
        admin.patch(
            f"/api/users/{users['candidate'].id}", {"role": "employee", **reason}, format="json"
        ).status_code
        == 400
    )
    assert (
        admin.patch(f"/api/users/{users['admin'].id}", {"is_active": False}, format="json").status_code == 400
    )


def test_admin_assigns_reporting_managers_without_loops(users, team):
    admin = as_user(users["admin"])
    me = team["me"]
    ok = admin.patch(f"/api/users/{me.user.id}", {"manager": str(team["lead"].id)}, format="json")
    assert ok.status_code == 200 and ok.data["employee"]["manager"]["id"] == str(team["lead"].id)
    me.refresh_from_db()
    assert me.manager == team["lead"]
    loop = admin.patch(
        f"/api/users/{team['boss'].user.id}", {"manager": str(team["junior"].id)}, format="json"
    )
    assert loop.status_code == 400 and "loop" in str(loop.data)
    own = admin.patch(f"/api/users/{me.user.id}", {"manager": str(me.id)}, format="json")
    assert own.status_code == 400


def test_admin_changes_locked_fields_only_with_a_reason(users, team):
    admin = as_user(users["admin"])
    person = team["me"].user
    change = {
        "full_name": "Divya P. Pillai",
        "employee_code": "LW2001",
        "joined_on": "2023-02-01",
        "date_of_birth": "1995-03-09",
    }
    assert admin.patch(f"/api/users/{person.id}", change, format="json").status_code == 400
    done = admin.patch(
        f"/api/users/{person.id}", {**change, "reason": "Legal name change, documents on file"}, format="json"
    )
    assert done.status_code == 200, done.data
    person.refresh_from_db()
    emp = Employee.objects.get(user=person)
    assert (
        person.full_name == "Divya P. Pillai" and emp.code == "LW2001" and str(emp.joined_on) == "2023-02-01"
    )
    assert Profile.objects.get(user=person).date_of_birth == "1995-03-09"
    log = AuditLog.objects.get(action="users.override", target_id=str(person.id))
    assert set(log.meta["fields"]) == {"full_name", "employee_code", "joined_on", "date_of_birth"}
    assert "1995" not in str(log.meta)  # values are never written to the audit log
    assert as_user(users["admin"]).get(f"/api/users/{person.id}").data["date_of_birth"] == "1995-03-09"


def test_deactivated_people_cannot_sign_in_or_use_old_sessions(users):
    target = users["employee"]
    client = APIClient()
    assert (
        client.post(
            "/api/auth/login", {"email": target.email, "password": PASSWORD}, format="json"
        ).status_code
        == 200
    )
    response = as_user(users["admin"]).patch(f"/api/users/{target.id}", {"is_active": False}, format="json")
    assert response.status_code == 200 and response.data["is_active"] is False
    assert client.get("/api/auth/me").status_code == 401  # the existing cookie no longer works
    again = APIClient().post("/api/auth/login", {"email": target.email, "password": PASSWORD}, format="json")
    assert again.status_code == 401


def test_people_are_never_hard_deleted(users):
    admin = as_user(users["admin"])
    # No delete action exists in the policy, so the request is refused before any view runs.
    assert admin.delete(f"/api/users/{users['employee'].id}").status_code in (403, 405)
    assert User.objects.filter(pk=users["employee"].pk).exists()


def test_admin_lists_people_with_their_employee_record(users, team):
    data = as_user(users["admin"]).get("/api/users?role=employee").data
    row = next(r for r in data["results"] if r["id"] == str(users["employee"].id))
    assert row["employee"]["manager"]["name"] == team["boss"].user.full_name
    assert as_user(users["hr"]).get("/api/users").status_code == 403

"""HR settings (hr_admin): leave types, holidays and work policy are data;
documents are checked by content; the needs-attention list."""

from datetime import date, timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import AuditLog
from hr import leave as engine
from hr.models import Holiday, LeaveType, WorkPolicy
from interviews.timeutil import today_ist


def as_user(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.mark.django_db
def test_hr_admin_edits_leave_rules_as_data(team, users):
    admin = as_user(users["hr_admin"])
    casual = LeaveType.objects.get(location=team["me"].location, code="casual")
    response = admin.patch(
        f"/api/hr/config/leave-types/{casual.id}",
        {"min_notice_days": 3, "sandwich_rule": True, "yearly_quota": 14.3},
        format="json",
    )
    assert response.status_code == 200
    casual.refresh_from_db()
    assert casual.min_notice_days == 3 and casual.sandwich_rule is True
    assert float(casual.yearly_quota) == 14.5  # half-day steps
    assert "Notice: 3 days." in response.data["summary"]
    assert AuditLog.objects.filter(action="hr.leave_type_updated").exists()
    bad = admin.patch(f"/api/hr/config/leave-types/{casual.id}", {"min_notice_days": -1}, format="json")
    assert bad.status_code == 400


@pytest.mark.django_db
def test_holiday_calendar_per_location(team, users, org):
    admin = as_user(users["hr_admin"])
    loc = org["location"]
    created = admin.post(
        "/api/hr/config/holidays",
        {"location": str(loc.id), "date": "2030-06-02", "name": "Telangana Formation Day", "regional": True},
        format="json",
    )
    assert created.status_code == 201
    again = admin.post(
        "/api/hr/config/holidays",
        {"location": str(loc.id), "date": "2030-06-02", "name": "Dup"},
        format="json",
    )
    assert again.status_code == 400
    assert not Holiday.objects.filter(location=org["location2"]).exists()
    assert admin.delete(f"/api/hr/config/holidays/{created.data['id']}").status_code == 204


@pytest.mark.django_db
def test_work_policy_validation(team, users, org):
    admin = as_user(users["hr_admin"])
    url = f"/api/hr/config/work-policy/{org['location'].id}"
    ok = admin.patch(
        url, {"shift_start": "10:00", "shift_end": "19:00", "min_team_available_pct": 60}, format="json"
    )
    assert ok.status_code == 200 and ok.data["shift_start"] == "10:00"
    assert WorkPolicy.objects.get(location=org["location"]).min_team_available_pct == 60
    assert admin.patch(url, {"shift_end": "08:00"}, format="json").status_code == 400
    assert admin.patch(url, {"weekly_off": [8]}, format="json").status_code == 400
    assert admin.patch(url, {"min_team_available_pct": 101}, format="json").status_code == 400


@pytest.mark.django_db
def test_policies_page_shows_my_location_rules(team):
    data = as_user(team["me"].user).get("/api/hr/policies").data
    assert data["location"]["name"] == team["me"].location.name
    assert {lt["code"] for lt in data["leave_types"]} >= {"casual", "sick", "earned", "comp_off", "lop"}
    assert data["handbook"] and data["work_policy"]["shift_start"] == "09:30"


def weekday_ahead(days):
    day = today_ist(timezone.now()) + timedelta(days=days)
    while day.isoweekday() > 5:
        day += timedelta(days=1)
    return day


@pytest.mark.django_db
def test_leave_documents_are_checked_by_content(team):
    me = team["me"]
    engine.credit_entitlements(me, today_ist(timezone.now()))
    client = as_user(me.user)
    start = weekday_ahead(14)
    fake = SimpleUploadedFile("cert.pdf", b"not really a pdf", content_type="application/pdf")
    response = client.post(
        "/api/leave/requests",
        {"leave_type": "lop", "start": start.isoformat(), "end": start.isoformat(), "document": fake},
        format="multipart",
    )
    assert response.status_code == 400 and "document" in response.data
    real = SimpleUploadedFile("cert.pdf", b"%PDF-1.4 demo", content_type="application/pdf")
    response = client.post(
        "/api/leave/requests",
        {"leave_type": "lop", "start": start.isoformat(), "end": start.isoformat(), "document": real},
        format="multipart",
    )
    assert response.status_code == 201 and response.data["has_document"] is True
    doc = client.get(f"/api/leave/requests/{response.data['id']}/document")
    assert doc.status_code == 200 and doc.content.startswith(b"%PDF")
    assert (
        as_user(team["peers"][1].user).get(f"/api/leave/requests/{response.data['id']}/document").status_code
        == 404
    )


@pytest.mark.django_db
def test_needs_attention_lists_escalations_and_overdue_tasks(team, users):
    from hr.models import OnboardingTask

    OnboardingTask.objects.create(
        employee=team["me"],
        title="Verify documents",
        category="documents",
        owner_kind="hr",
        kind="task",
        due_on=date(2020, 1, 1),
    )
    data = as_user(users["hr_admin"]).get("/api/hr/attention").data
    assert data["overdue_tasks"][0]["title"] == "Verify documents"
    assert "leave" in data and "no_buddy" in data


@pytest.mark.django_db
def test_hr_adjusts_comp_off(team, users):
    admin = as_user(users["hr_admin"])
    response = admin.post(
        "/api/leave/adjust",
        {
            "employee": str(team["me"].id),
            "leave_type": "comp_off",
            "days": 1,
            "note": "Worked on Saturday release",
        },
        format="json",
    )
    assert response.status_code == 201
    comp = next(r for r in response.data["balances"] if r["type"] == "comp_off")
    assert comp["balance"] == 1.0
    assert (
        admin.post(
            "/api/leave/adjust",
            {"employee": str(team["me"].id), "leave_type": "lop", "days": 1, "note": "nope nope"},
            format="json",
        ).status_code
        == 400
    )

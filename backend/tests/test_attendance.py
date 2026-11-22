"""Attendance: late and early flags, missing check-out, regularisation by the
reporting manager, monthly summaries and scope."""

from datetime import date, datetime, time, timedelta

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from hr import attendance
from hr.models import AttendanceRecord, Regularisation, RegularisationStatus
from interviews.timeutil import IST, today_ist

DAY = date(2026, 3, 3)  # Tuesday; shift 09:30-18:30, 15 minutes grace each way


def at(day, hh, mm):
    return datetime.combine(day, time(hh, mm), tzinfo=IST)


def as_user(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def last_working_day():
    day = today_ist(timezone.now()) - timedelta(days=1)
    while day.isoweekday() in (6, 7):
        day -= timedelta(days=1)
    return day


@pytest.mark.django_db
def test_late_and_early_flags_use_the_shift_and_grace(team):
    me = team["me"]
    on_time = attendance.check_in(me, "office", now=at(DAY, 9, 44))
    assert on_time.late is False
    out = attendance.check_out(me, now=at(DAY, 18, 16))
    assert out.early is False

    next_day = DAY + timedelta(days=1)
    late = attendance.check_in(me, "remote", now=at(next_day, 9, 46))
    assert late.late is True and late.mode == "remote"
    early = attendance.check_out(me, now=at(next_day, 18, 14))
    assert early.early is True


@pytest.mark.django_db
def test_check_in_once_and_check_out_after_check_in(team):
    me = team["me"]
    with pytest.raises(ValidationError):
        attendance.check_out(me, now=at(DAY, 18, 0))
    attendance.check_in(me, "office", now=at(DAY, 9, 30))
    with pytest.raises(ValidationError):
        attendance.check_in(me, "office", now=at(DAY, 10, 0))
    with pytest.raises(ValidationError):
        attendance.check_in(team["peers"][1], "moon", now=at(DAY, 10, 0))
    attendance.check_out(me, now=at(DAY, 18, 30))
    with pytest.raises(ValidationError):
        attendance.check_out(me, now=at(DAY, 19, 0))


@pytest.mark.django_db
def test_missing_checkouts_are_flagged_once(team):
    from notifications.models import Notification

    me = team["me"]
    attendance.check_in(me, "office", now=at(DAY, 9, 30))
    assert attendance.mark_missing_checkouts(now=at(DAY, 23, 0)) == 0  # same day: not yet
    assert attendance.mark_missing_checkouts(now=at(DAY + timedelta(days=1), 1, 0)) == 1
    assert attendance.mark_missing_checkouts(now=at(DAY + timedelta(days=2), 1, 0)) == 0
    assert AttendanceRecord.objects.get(employee=me, date=DAY).missing_checkout is True
    assert Notification.objects.filter(user=me.user, kind="attendance_missing").count() == 1


@pytest.mark.django_db
def test_regularisation_goes_to_the_reporting_manager(team):
    me, boss, peer = team["me"], team["boss"], team["peers"][1]
    day = last_working_day()
    response = as_user(me.user).post(
        "/api/attendance/regularisations",
        {
            "date": day.isoformat(),
            "check_in": "09:35",
            "check_out": "18:40",
            "mode": "office",
            "reason": "Forgot to check out",
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    reg = Regularisation.objects.get()
    assert reg.approver == boss.user

    assert (
        as_user(me.user)
        .post(f"/api/attendance/regularisations/{reg.id}/decide", {"decision": "approve"}, format="json")
        .status_code
        == 403
    )
    assert (
        as_user(peer.user)
        .post(f"/api/attendance/regularisations/{reg.id}/decide", {"decision": "approve"}, format="json")
        .status_code
        == 404
    )
    assert as_user(boss.user).get("/api/leave/approvals").data["regularisations"][0]["id"] == str(reg.id)

    decided = as_user(boss.user).post(
        f"/api/attendance/regularisations/{reg.id}/decide", {"decision": "approve"}, format="json"
    )
    assert decided.status_code == 200 and decided.data["status"] == RegularisationStatus.APPROVED
    record = AttendanceRecord.objects.get(employee=me, date=day)
    assert record.regularised and not record.missing_checkout and not record.late


@pytest.mark.django_db
def test_regularisation_rules(team):
    me = team["me"]
    today = today_ist(timezone.now())

    def ask(**data):
        base = {
            "date": last_working_day().isoformat(),
            "check_in": "09:30",
            "check_out": "18:30",
            "reason": "Network down",
        }
        return attendance.request_regularisation(me, {**base, **data})

    for bad in (
        {"date": today.isoformat()},
        {"date": (today - timedelta(days=40)).isoformat()},
        {"check_out": "09:00"},
        {"reason": "no"},
        {"mode": "beach"},
    ):
        with pytest.raises(ValidationError):
            ask(**bad)
    ask()
    with pytest.raises(ValidationError):
        ask()  # one pending request per day


@pytest.mark.django_db
def test_rejecting_needs_a_reason(team):
    me, boss = team["me"], team["boss"]
    reg = attendance.request_regularisation(
        me,
        {
            "date": last_working_day().isoformat(),
            "check_in": "09:30",
            "check_out": "18:30",
            "reason": "Forgot",
        },
    )
    with pytest.raises(ValidationError):
        attendance.decide(reg, boss.user, approve=False, note="")
    attendance.decide(reg, boss.user, approve=False, note="No badge record that day")
    reg.refresh_from_db()
    assert reg.status == RegularisationStatus.REJECTED
    assert not AttendanceRecord.objects.filter(employee=me, regularised=True).exists()


@pytest.mark.django_db
def test_monthly_summary_counts(team):
    me = team["me"]
    attendance.check_in(me, "office", now=at(DAY, 9, 50))
    attendance.check_out(me, now=at(DAY, 18, 0))
    attendance.check_in(me, "remote", now=at(DAY + timedelta(days=1), 9, 30))
    data = attendance.summary(me, date(2026, 3, 1), today=date(2026, 3, 6))
    counts = data["counts"]
    assert counts["present"] == 2 and counts["office"] == 1 and counts["remote"] == 1
    assert counts["late"] == 1 and counts["early"] == 1
    assert counts["working_days"] == 5 and counts["absent"] == 2  # 2 Mar and 5 Mar; 6 Mar is today


@pytest.mark.django_db
def test_team_summary_scope(team):
    boss, me, hr, junior = team["boss"], team["me"], team["hr"], team["junior"]
    names = {row["name"] for row in as_user(boss.user).get("/api/attendance/team").data["rows"]}
    assert me.name in names and junior.name not in names and boss.name not in names
    assert as_user(me.user).get("/api/attendance/team").data["rows"] == []
    everyone = as_user(hr.user).get("/api/attendance/team").data
    assert everyone["scope"] == "all" and len(everyone["rows"]) >= 7


@pytest.mark.django_db
def test_check_in_over_the_api(team):
    me = team["me"]
    response = as_user(me.user).post("/api/attendance/check-in", {"mode": "remote"}, format="json")
    assert response.status_code == 201 and response.data["mode"] == "remote"
    data = as_user(me.user).get("/api/attendance/me").data
    assert data["today"]["check_in"] and data["shift"]["start"] == "09:30"
    assert "location" in data["shift"] and "latitude" not in str(data)  # no location tracking

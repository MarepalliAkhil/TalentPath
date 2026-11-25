"""Correctness does not depend on the cron tick: the parts that matter are also applied on read.

- interviews: expired holds are released and finished interviews become completed when interviews
  are read (so scorecards can be submitted);
- leave: due accruals are credited when balances are read or leave is applied for; delegation and
  48-hour escalation are applied when approvals are read;
- attendance: a past day without a check-out counts as missing before the nightly flag.
"""

from datetime import date, datetime, time, timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from hr import leave as engine
from hr.models import AttendanceRecord, LeaveLedger, LeaveRequest
from interviews.models import Interview, InterviewStatus
from interviews.timeutil import IST, today_ist


def as_user(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.mark.django_db
def test_finished_interviews_complete_when_read_without_the_tick(application, users):
    from interviews.coordinator import get_plan

    past = timezone.now() - timedelta(hours=3)
    interview = Interview.objects.create(
        application=application,
        round=get_plan(application.job).rounds.first(),
        status=InterviewStatus.SCHEDULED,
        starts_at=past,
        ends_at=past + timedelta(hours=1),
    )
    response = as_user(users["recruiter"]).get(f"/api/applications/{application.id}/interviews")
    assert response.status_code == 200
    interview.refresh_from_db()
    assert interview.status == InterviewStatus.COMPLETED


@pytest.mark.django_db
def test_balances_are_credited_on_read_without_the_nightly_job(make_employee):
    emp = make_employee(joined=date(2024, 1, 15))
    assert not LeaveLedger.objects.filter(employee=emp).exists()
    data = as_user(emp.user).get("/api/leave/balances").data
    casual = next(b for b in data["balances"] if b["type"] == "casual")
    assert casual["balance"] == float(today_ist(timezone.now()).month)  # 1 day a month so far
    as_user(emp.user).get("/api/leave/balances")  # reading again credits nothing twice
    casual_rows = LeaveLedger.objects.filter(employee=emp, kind="accrual", leave_type__code="casual")
    assert casual_rows.count() == today_ist(timezone.now()).month


@pytest.mark.django_db
def test_escalation_happens_when_approvals_are_read(team):
    junior, boss = team["junior"], team["boss"]
    today = today_ist(timezone.now())
    engine.credit_entitlements(junior, today)
    start = today + timedelta(days=21)
    while start.isoweekday() > 5:
        start += timedelta(days=1)
    leave = engine.apply(junior, junior.user, {"leave_type": "lop", "start": start.isoformat()})
    LeaveRequest.objects.filter(pk=leave.pk).update(assigned_at=timezone.now() - timedelta(hours=49))
    rows = as_user(boss.user).get("/api/leave/approvals").data["leave"]
    leave.refresh_from_db()
    assert leave.escalated is True and leave.approver == boss.user
    assert [r["id"] for r in rows] == [str(leave.id)]


@pytest.mark.django_db
def test_missing_checkout_counts_before_the_nightly_flag(make_employee):
    from hr.attendance import summary

    emp = make_employee()
    day = date(2026, 3, 3)
    AttendanceRecord.objects.create(
        employee=emp,
        date=day,
        check_in=datetime.combine(day, time(9, 30), tzinfo=IST),
        missing_checkout=False,
    )
    data = summary(emp, date(2026, 3, 1), today=date(2026, 3, 5))
    assert data["counts"]["missing_checkout"] == 1
    assert next(d for d in data["days"] if d["date"] == "2026-03-03")["missing_checkout"] is True

"""Leave approvals: reporting line (not role), HR threshold, delegation,
escalation, cancellation, own-leave rules, privacy of reasons, team calendar
and clash warnings."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient

from hr import leave as engine
from hr import team as team_rules
from hr.models import ApprovalStage, LeaveLedger, LeaveRequest, LeaveStatus, LeaveType, WorkPolicy
from interviews.timeutil import today_ist

TODAY = date(2026, 3, 2)  # Monday
NOW = engine.as_datetime(TODAY)


def as_user(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def staff(team):
    for emp in [team["boss"], team["me"], *team["peers"], team["junior"], team["hr"], team["recruiter"]]:
        engine.credit_entitlements(emp, TODAY)
    return team


def apply(emp, *, code="casual", start="2026-03-10", end=None, now=NOW, **extra):
    data = {"leave_type": code, "start": start, "end": end or start, "reason": "Family function", **extra}
    return engine.apply(emp, emp.user, data, now=now)


def approved_leave(emp, start: date, end: date, code="lop"):
    return LeaveRequest.objects.create(
        employee=emp,
        leave_type=LeaveType.objects.get(location=emp.location, code=code),
        start=start,
        end=end,
        days=Decimal((end - start).days + 1),
        status=LeaveStatus.APPROVED,
    )


@pytest.mark.django_db
def test_reporting_manager_approves_and_balance_is_used(staff):
    me, boss = staff["me"], staff["boss"]
    leave = apply(me)
    assert leave.status == LeaveStatus.PENDING and leave.approver == boss.user
    assert leave.stage == ApprovalStage.MANAGER
    engine.approve(leave, boss.user, now=NOW)
    leave.refresh_from_db()
    assert leave.status == LeaveStatus.APPROVED and leave.manager_approved_by == boss.user
    use = LeaveLedger.objects.get(key=f"use:{leave.id}")
    assert use.days == Decimal("-1")
    assert [a.action for a in leave.actions.all()] == ["submitted", "assigned", "approved"]


@pytest.mark.django_db
def test_the_reporting_line_decides_not_the_role(staff):
    junior, lead = staff["junior"], staff["lead"]
    assert lead.user.role == "employee"
    leave = apply(junior)
    assert leave.approver == lead.user
    with pytest.raises(PermissionDenied):
        engine.approve(leave, staff["boss"].user, now=NOW)  # a hiring manager, but not junior's manager
    engine.approve(leave, lead.user, now=NOW)
    leave.refresh_from_db()
    assert leave.status == LeaveStatus.APPROVED


@pytest.mark.django_db
def test_nobody_approves_their_own_leave(staff):
    hr = staff["hr"]  # reports to nobody: goes to HR, but not to themselves
    leave = apply(hr)
    assert leave.stage == ApprovalStage.HR and leave.approver is None
    assert engine.can_act(leave, hr.user) is False
    assert leave not in engine.approvals_for(hr.user)
    with pytest.raises(PermissionDenied):
        engine.approve(leave, hr.user, now=NOW)
    response = as_user(staff["me"].user).post(
        f"/api/leave/requests/{apply(staff['me'], start='2026-03-11').id}/approve", {}, format="json"
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_long_leave_also_needs_hr(staff):
    me, boss, hr = staff["me"], staff["boss"], staff["hr"]
    leave = apply(me, code="lop", start="2026-03-09", end="2026-03-17")  # 7 working days > 5
    engine.approve(leave, boss.user, now=NOW)
    leave.refresh_from_db()
    assert leave.status == LeaveStatus.PENDING and leave.stage == ApprovalStage.HR
    assert leave.manager_approved_by == boss.user and leave.approver is None
    assert leave in engine.approvals_for(hr.user)
    engine.approve(leave, hr.user, now=NOW)
    leave.refresh_from_db()
    assert leave.status == LeaveStatus.APPROVED and leave.decided_by == hr.user


@pytest.mark.django_db
def test_threshold_is_configurable(staff):
    WorkPolicy.objects.filter(location=staff["me"].location).update(hr_approval_over_days=Decimal("10"))
    leave = apply(staff["me"], code="lop", start="2026-03-09", end="2026-03-17")
    engine.approve(leave, staff["boss"].user, now=NOW)
    leave.refresh_from_db()
    assert leave.status == LeaveStatus.APPROVED


@pytest.mark.django_db
def test_rejection_needs_a_reason(staff):
    leave = apply(staff["me"])
    with pytest.raises(ValidationError):
        engine.reject(leave, staff["boss"].user, "", now=NOW)
    engine.reject(leave, staff["boss"].user, "Release week, please move it", now=NOW)
    leave.refresh_from_db()
    assert leave.status == LeaveStatus.REJECTED
    assert not LeaveLedger.objects.filter(key=f"use:{leave.id}").exists()


@pytest.mark.django_db
def test_delegation_when_the_approver_is_on_leave(staff):
    junior, lead, boss = staff["junior"], staff["lead"], staff["boss"]
    approved_leave(lead, TODAY, TODAY + timedelta(days=4))
    leave = apply(junior)
    assert leave.approver == boss.user and leave.delegated is True


@pytest.mark.django_db
def test_pending_requests_move_when_the_approver_goes_on_leave(staff):
    junior, lead, boss = staff["junior"], staff["lead"], staff["boss"]
    leave = apply(junior)
    assert leave.approver == lead.user
    approved_leave(lead, TODAY + timedelta(days=1), TODAY + timedelta(days=3))
    assert engine.refresh_delegations(NOW + timedelta(days=1)) == 1
    leave.refresh_from_db()
    assert leave.approver == boss.user and leave.delegated is True
    assert leave.actions.filter(action="assigned", detail__contains="delegated").exists()


@pytest.mark.django_db
def test_escalation_after_48_hours(staff):
    junior, boss, hr = staff["junior"], staff["boss"], staff["hr"]
    leave = apply(junior)
    assert engine.escalate_due(NOW + timedelta(hours=47)) == 0
    assert engine.escalate_due(NOW + timedelta(hours=49)) == 1
    leave.refresh_from_db()
    assert leave.escalated is True and leave.approver == boss.user
    assert leave in engine.needs_attention()
    assert engine.can_act(leave, hr.user)  # hr_admin can step in on escalated requests
    # Still waiting 48 hours later: up again; boss reports to nobody, so HR.
    engine.escalate_due(NOW + timedelta(hours=98))
    leave.refresh_from_db()
    assert leave.approver is None and leave.stage == ApprovalStage.HR


@pytest.mark.django_db
def test_cancel_before_the_start_returns_the_days(staff):
    me, boss = staff["me"], staff["boss"]
    leave = apply(me)
    engine.approve(leave, boss.user, now=NOW)
    casual = LeaveType.objects.get(location=me.location, code="casual")
    before = engine.ledger_total(me, casual, 2026)
    engine.cancel(leave, me.user, now=NOW)
    leave.refresh_from_db()
    assert leave.status == LeaveStatus.CANCELLED
    assert engine.ledger_total(me, casual, 2026) == before + 1
    with pytest.raises(ValidationError):
        engine.cancel(leave, me.user, now=NOW)


@pytest.mark.django_db
def test_cannot_cancel_on_or_after_the_start_or_someone_elses(staff):
    leave = apply(staff["me"])
    with pytest.raises(PermissionDenied):
        engine.cancel(leave, staff["boss"].user, now=NOW)
    with pytest.raises(ValidationError):
        engine.cancel(leave, staff["me"].user, now=engine.as_datetime(date(2026, 3, 10)))


# ---------------------------------------------------------------- privacy over the API
def future_monday(weeks=3):
    today = today_ist(timezone.now())
    day = today + timedelta(days=7 * weeks)
    return day - timedelta(days=day.weekday())


@pytest.mark.django_db
def test_peers_never_see_reasons_managers_do(staff):
    me, boss, peer = staff["me"], staff["boss"], staff["peers"][1]
    start = future_monday()
    response = as_user(me.user).post(
        "/api/leave/requests",
        {
            "leave_type": "lop",
            "start": start.isoformat(),
            "end": start.isoformat(),
            "reason": "Hospital visit",
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    leave_id = response.data["id"]
    assert as_user(peer.user).get(f"/api/leave/requests/{leave_id}").status_code == 404
    assert as_user(boss.user).get(f"/api/leave/requests/{leave_id}").data["reason"] == "Hospital visit"

    month = start.strftime("%Y-%m")
    peer_view = as_user(peer.user).get(f"/api/team-calendar?month={month}").data
    entry = next(e for e in peer_view["entries"] if e["id"] == leave_id)
    assert entry["reason"] is None and entry["type"] is None and peer_view["sees_reasons"] is False
    boss_view = as_user(boss.user).get(f"/api/team-calendar?month={month}&view=reports").data
    entry = next(e for e in boss_view["entries"] if e["id"] == leave_id)
    assert entry["reason"] == "Hospital visit" and boss_view["sees_reasons"] is True

    approvals = as_user(boss.user).get("/api/leave/approvals").data
    assert [row["id"] for row in approvals["leave"]] == [leave_id]
    assert as_user(peer.user).get("/api/leave/approvals").data["leave"] == []


@pytest.mark.django_db
def test_only_hr_or_the_manager_can_view_another_team(staff):
    boss = staff["boss"]
    assert as_user(staff["peers"][1].user).get(f"/api/team-calendar?manager={boss.id}").status_code == 404
    assert as_user(staff["hr"].user).get(f"/api/team-calendar?manager={boss.id}").status_code == 200
    assert as_user(boss.user).get(f"/api/team-calendar?manager={boss.id}").status_code == 200


@pytest.mark.django_db
def test_preview_shows_the_days_counted_before_submitting(staff):
    start = future_monday()
    data = (
        as_user(staff["me"].user)
        .post(
            "/api/leave/preview",
            {"leave_type": "lop", "start": start.isoformat(), "end": (start + timedelta(days=7)).isoformat()},
            format="json",
        )
        .data
    )
    # Monday to the next Monday: 6 working days plus the weekend between them (LOP has the sandwich rule).
    assert data["ok"] is True and data["days"] == 8.0
    assert data["days_label"] == "8 days" and data["needs_hr_approval"] is True
    assert [row["kind"] for row in data["breakdown"]].count("sandwich") == 2
    assert not LeaveRequest.objects.exists()  # preview never saves


# ---------------------------------------------------------------- clash warnings
@pytest.mark.django_db
def test_clash_warning_below_the_threshold(staff):
    me, peers = staff["me"], staff["peers"]
    day = date(2026, 3, 12)
    assert len(team_rules.team_members(me)) == 4
    approved_leave(peers[0], day, day)
    assert team_rules.clash_warnings(me, [day]) == []  # 2 of 4 would still be in: 50% is fine
    approved_leave(peers[1], day, day)
    warnings = team_rules.clash_warnings(me, [day])
    assert len(warnings) == 1
    assert warnings[0].startswith("2 of 4 people in") and "Thu 12 Mar" in warnings[0]
    assert "1 would be available" in warnings[0]


@pytest.mark.django_db
def test_threshold_change_changes_the_warning(staff):
    me, peers = staff["me"], staff["peers"]
    day = date(2026, 3, 12)
    approved_leave(peers[0], day, day)
    WorkPolicy.objects.filter(location=me.location).update(min_team_available_pct=75)
    assert len(team_rules.clash_warnings(me, [day])) == 1


@pytest.mark.django_db
def test_warnings_inform_but_do_not_block(staff):
    me, peers = staff["me"], staff["peers"]
    day = date(2026, 3, 12)
    approved_leave(peers[0], day, day)
    approved_leave(peers[1], day, day)
    result = engine.check(me, {"leave_type": "casual", "start": "2026-03-12"}, today=TODAY)
    assert result.warnings and result.errors == {}
    leave = apply(me, start="2026-03-12")
    assert leave.status == LeaveStatus.PENDING
    # The manager sees the same warning while approving.
    payload = as_user(staff["boss"].user).get(f"/api/leave/requests/{leave.id}").data
    assert payload["warnings"] and payload["warnings"][0].startswith("2 of 4")


@pytest.mark.django_db
def test_rejected_and_cancelled_leave_do_not_count_as_off(staff):
    me, peers = staff["me"], staff["peers"]
    day = date(2026, 3, 12)
    approved_leave(peers[0], day, day)
    gone = approved_leave(peers[1], day, day)
    gone.status = LeaveStatus.CANCELLED
    gone.save()
    assert team_rules.clash_warnings(me, [day]) == []

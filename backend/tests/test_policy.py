"""Permission matrix driven by shared/policy.json.

For every endpoint and every principal (5 roles + anonymous) the request must be
allowed exactly when the policy says so: denied anonymous calls answer 401,
denied signed-in calls answer 403, and cron endpoints refuse anyone without the
secret header.
"""

from collections import namedtuple

import pytest
from django.urls import get_resolver

from core.permissions import resolve_action
from core.policy import INTERNAL, allowed_principals, load_policy
from core.views import PolicyAPIView
from notifications.models import Notification

from .conftest import PRINCIPALS

E = namedtuple("E", "action method path")

ORG = [("departments", "department"), ("locations", "location"), ("job-levels", "level"), ("skills", "skill")]

ENDPOINTS = [
    E("system.ping", "get", "/api/ping"),
    E("system.tick", "post", "/api/internal/tick"),
    E("system.nightly", "post", "/api/internal/nightly"),
    E("seo.sitemap", "get", "/sitemap.xml"),
    E("seo.robots", "get", "/robots.txt"),
    E("auth.csrf", "get", "/api/auth/csrf"),
    E("auth.register", "post", "/api/auth/register"),
    E("auth.login", "post", "/api/auth/login"),
    E("auth.logout", "post", "/api/auth/logout"),
    E("auth.refresh", "post", "/api/auth/refresh"),
    E("auth.me", "get", "/api/auth/me"),
    E("auth.password_reset", "post", "/api/auth/password-reset"),
    E("auth.password_reset_confirm", "post", "/api/auth/password-reset/confirm"),
    E("profile.read", "get", "/api/profile"),
    E("profile.update", "patch", "/api/profile"),
    E("users.list", "get", "/api/users"),
    E("users.create", "post", "/api/users"),
    E("users.update", "patch", "/api/users/{user}"),
    E("users.hiring_managers", "get", "/api/hiring-managers"),
    E("jobs.board", "get", "/api/jobs/{job}/board"),
    E("applications.bulk_status", "post", "/api/jobs/{job}/applications/bulk-status"),
    E("applications.notes", "get", "/api/applications/{app}/notes"),
    E("applications.notes", "post", "/api/applications/{app}/notes"),
    E("applications.reveal", "post", "/api/applications/{app}/reveal"),
    E("hira.ask", "post", "/api/hira/ask"),
    E("hira.message", "post", "/api/hira/message"),
    E("fairness.check", "get", "/api/fairness/check"),
    E("interviews.plan_read", "get", "/api/jobs/{job}/interview-plan"),
    E("interviews.plan_update", "put", "/api/jobs/{job}/interview-plan"),
    E("interviewers.list", "get", "/api/interviewers"),
    E("interviewers.update", "patch", "/api/interviewers/{user}"),
    E("availability.manage", "get", "/api/availability"),
    E("availability.manage", "put", "/api/availability"),
    E("availability.manage", "post", "/api/availability/blocks"),
    E("availability.manage", "delete", "/api/availability/blocks/{block}"),
    E("interviews.mine", "get", "/api/my/interviews"),
    E("interviews.assigned", "get", "/api/interviews/assigned"),
    E("interviews.for_application", "get", "/api/applications/{app}/interviews"),
    E("interviews.propose", "post", "/api/applications/{app}/interviews/propose"),
    E("interviews.schedule_manual", "post", "/api/applications/{app}/interviews/manual"),
    E("interviews.hold", "post", "/api/interviews/{interview}/hold"),
    E("interviews.confirm", "post", "/api/interviews/{interview}/confirm"),
    E("interviews.reschedule", "post", "/api/interviews/{interview}/reschedule"),
    E("interviews.decline", "post", "/api/interviews/{interview}/decline"),
    E("interviews.no_show", "post", "/api/interviews/{interview}/no-show"),
    E("interviews.calendar", "get", "/api/interviews/{interview}/calendar.ics"),
    E("schedule.link", "get", "/api/schedule/{token}"),
    E("schedule.link", "post", "/api/schedule/{token}/hold"),
    E("schedule.link", "post", "/api/schedule/{token}/confirm"),
    E("scorecards.read", "get", "/api/interviews/{interview}/scorecards"),
    E("scorecards.submit", "post", "/api/interviews/{interview}/scorecards"),
    E("hira.briefing", "get", "/api/hira/briefing"),
    E("hira.briefing", "post", "/api/hira/briefing"),
    E("hira.activity", "get", "/api/hira/activity"),
    E("hira.activity", "get", "/api/hira/activity/summary"),
    E("offers.list", "get", "/api/offers"),
    E("offers.create", "post", "/api/applications/{app}/offers"),
    E("offers.read", "get", "/api/offers/{offer}"),
    E("offers.update", "patch", "/api/offers/{offer}"),
    E("offers.submit", "post", "/api/offers/{offer}/submit"),
    E("offers.approve", "post", "/api/offers/{offer}/approve"),
    E("offers.reject", "post", "/api/offers/{offer}/reject"),
    E("offers.send", "post", "/api/offers/{offer}/send"),
    E("offers.revoke", "post", "/api/offers/{offer}/revoke"),
    E("offers.accept", "post", "/api/offers/{offer}/accept"),
    E("offers.decline", "post", "/api/offers/{offer}/decline"),
    E("offers.letter", "get", "/api/offers/{offer}/letter"),
    E("offers.mine", "get", "/api/my/offers"),
    # week 3B: hire to onboard, leave, team calendar, attendance, HR settings
    E("onboarding.hire", "post", "/api/offers/{offer}/hire"),
    E("onboarding.mine", "get", "/api/onboarding/me"),
    E("onboarding.mine", "post", "/api/onboarding/me"),
    E("onboarding.list", "get", "/api/onboarding"),
    E("onboarding.list", "get", "/api/onboarding/{emp}"),
    E("onboarding.task", "post", "/api/onboarding/tasks/{task}/complete"),
    E("onboarding.task", "post", "/api/onboarding/tasks/{task}/reopen"),
    E("onboarding.task", "get", "/api/onboarding/tasks/{task}/document"),
    E("leave.read", "get", "/api/leave/balances"),
    E("leave.apply", "post", "/api/leave/preview"),
    E("leave.read", "get", "/api/leave/requests"),
    E("leave.apply", "post", "/api/leave/requests"),
    E("leave.read", "get", "/api/leave/requests/{leave}"),
    E("leave.read", "get", "/api/leave/requests/{leave}/document"),
    E("leave.apply", "post", "/api/leave/requests/{leave}/cancel"),
    E("leave.approve", "post", "/api/leave/requests/{leave}/approve"),
    E("leave.approve", "post", "/api/leave/requests/{leave}/reject"),
    E("leave.approve", "get", "/api/leave/approvals"),
    E("leave.adjust", "post", "/api/leave/adjust"),
    E("team.calendar", "get", "/api/team-calendar"),
    E("hr.read", "get", "/api/hr/policies"),
    E("hr.attention", "get", "/api/hr/attention"),
    E("hr.config", "get", "/api/hr/config"),
    E("hr.config", "post", "/api/hr/config/leave-types"),
    E("hr.config", "patch", "/api/hr/config/leave-types/{leave_type}"),
    E("hr.config", "post", "/api/hr/config/holidays"),
    E("hr.config", "delete", "/api/hr/config/holidays/{holiday}"),
    E("hr.config", "patch", "/api/hr/config/work-policy/{work_policy}"),
    E("attendance.read", "get", "/api/attendance/me"),
    E("attendance.check", "post", "/api/attendance/check-in"),
    E("attendance.check", "post", "/api/attendance/check-out"),
    E("attendance.regularise", "post", "/api/attendance/regularisations"),
    E("attendance.approve", "post", "/api/attendance/regularisations/{reg}/decide"),
    E("attendance.team", "get", "/api/attendance/team"),
    *[
        endpoint
        for resource, key in ORG
        for endpoint in (
            E("org.read", "get", f"/api/{resource}"),
            E("org.manage", "post", f"/api/{resource}"),
            E("org.manage", "patch", f"/api/{resource}/{{{key}}}"),
            E("org.manage", "delete", f"/api/{resource}/{{{key}}}"),
        )
    ],
    E("careers.list", "get", "/api/public/jobs"),
    E("careers.detail", "get", "/api/public/jobs/{slug}"),
    E("jobs.list", "get", "/api/jobs"),
    E("jobs.create", "post", "/api/jobs"),
    E("jobs.read", "get", "/api/jobs/{job}"),
    E("jobs.update", "patch", "/api/jobs/{job}"),
    E("jobs.delete", "delete", "/api/jobs/{job}"),
    E("jobs.status", "post", "/api/jobs/{job}/status"),
    E("jobs.applications", "get", "/api/jobs/{job}/applications"),
    E("applications.create", "post", "/api/applications"),
    E("applications.list_mine", "get", "/api/applications"),
    E("applications.read", "get", "/api/applications/{app}"),
    E("applications.withdraw", "post", "/api/applications/{app}/withdraw"),
    E("applications.status", "post", "/api/applications/{app}/status"),
    E("applications.resume", "get", "/api/applications/{app}/resume"),
    E("notifications.list", "get", "/api/notifications"),
    E("notifications.read", "post", "/api/notifications/{notif}/read"),
    E("notifications.read_all", "post", "/api/notifications/read-all"),
    E("realtime.ticket", "post", "/api/realtime/ticket"),
    E("dashboard.summary", "get", "/api/dashboard/summary"),
    E("audit.list", "get", "/api/audit"),
    E("outbox.list", "get", "/api/outbox"),
    E("demo.inbox", "get", "/api/demo/inbox"),
]

POLICY_DENIAL_CODES = {"not_authenticated", "permission_denied"}


def denial_code(response):
    data = getattr(response, "data", None)
    if isinstance(data, dict) and "detail" in data:
        return getattr(data["detail"], "code", None)
    return None


@pytest.fixture
def world(users, org, skills, application, team):
    from datetime import timedelta

    from django.utils import timezone

    from interviews import tokens
    from interviews.coordinator import get_plan
    from interviews.models import BlockedTime, Interview
    from offers.models import Offer

    job = application.job
    interview = Interview.objects.create(application=application, round=get_plan(job).rounds.first())
    offer = Offer(
        application=application,
        expires_on=timezone.now().date() + timedelta(days=5),
        created_by=users["recruiter"],
    )
    offer.data = {"designation": "Engineer", "fixed_pay": 100, "variable_pay": 0}
    offer.save()
    soon = timezone.now() + timedelta(days=1)
    block = BlockedTime.objects.create(
        user=users["employee"], starts_at=soon, ends_at=soon + timedelta(hours=1)
    )
    from datetime import date, time

    from hr.models import Holiday, LeaveRequest, LeaveType, OnboardingTask, Regularisation, WorkPolicy

    me = team["me"]
    leave_type = LeaveType.objects.get(location=me.location, code="casual")
    leave = LeaveRequest.objects.create(
        employee=team["junior"], leave_type=leave_type, start=date(2030, 3, 4), end=date(2030, 3, 4), days=1
    )
    task = OnboardingTask.objects.create(
        employee=me, title="Upload ID", category="documents", owner_kind="employee", owner=me.user,
        kind="upload", due_on=date(2030, 1, 2),
    )
    reg = Regularisation.objects.create(
        employee=team["junior"],
        date=date(2026, 1, 5),
        check_in=time(9, 30),
        check_out=time(18, 30),
        reason="Forgot",
    )
    holiday = Holiday.objects.create(location=me.location, date=date(2030, 8, 15), name="Independence Day")
    return {
        "emp": me.id,
        "task": task.id,
        "leave": leave.id,
        "reg": reg.id,
        "holiday": holiday.id,
        "leave_type": leave_type.id,
        "work_policy": WorkPolicy.objects.get(location=me.location).id,
        "interview": interview.id,
        "offer": offer.id,
        "block": block.id,
        "token": tokens.issue(interview),
        "user": users["employee"].id,
        "department": org["department"].id,
        "location": org["location"].id,
        "level": org["level"].id,
        "skill": skills["kubernetes"].id,
        "slug": job.slug,
        "job": job.id,
        "app": application.id,
        "notif": Notification.objects.filter(user=users["candidate"]).first().id,
    }


@pytest.mark.parametrize("principal", PRINCIPALS)
@pytest.mark.parametrize("endpoint", ENDPOINTS, ids=lambda e: f"{e.method.upper()} {e.path}")
def test_policy_matrix(endpoint, principal, world, client_for):
    client = client_for(principal)
    url = endpoint.path.format(**world)
    response = getattr(client, endpoint.method)(url, {}, format="json")
    allowed = allowed_principals(endpoint.action)

    if INTERNAL in allowed:
        assert response.status_code == 403, "cron endpoints need the secret header"
        return
    if principal in allowed:
        assert response.status_code < 500
        assert denial_code(response) not in POLICY_DENIAL_CODES, (
            f"{principal} should be allowed {endpoint.action}, got {response.status_code}"
        )
    else:
        expected = 401 if principal == "anonymous" else 403
        assert response.status_code == expected, (
            f"{principal} must be denied {endpoint.action}, got {response.status_code}"
        )
        assert denial_code(response) in POLICY_DENIAL_CODES


def _routed_views():
    def walk(patterns):
        for pattern in patterns:
            if hasattr(pattern, "url_patterns"):
                yield from walk(pattern.url_patterns)
            else:
                yield pattern

    for pattern in walk(get_resolver().url_patterns):
        cls = getattr(pattern.callback, "cls", None)
        yield pattern, cls, getattr(pattern.callback, "initkwargs", {})


def test_every_route_is_a_policy_view_with_known_actions():
    known = set(load_policy()["actions"])
    routed = set()
    for pattern, cls, initkwargs in _routed_views():
        assert cls is not None and issubclass(cls, PolicyAPIView), f"{pattern} bypasses the policy"
        view = cls(**initkwargs)
        for method in ("get", "post", "put", "patch", "delete"):
            if hasattr(view, method):
                action = resolve_action(view, method.upper())
                assert action in known, f"{pattern} {method} maps to unknown action {action!r}"
                routed.add(action)
    assert routed == known, f"policy actions without a route: {known - routed}"


def test_matrix_covers_every_policy_action():
    assert {e.action for e in ENDPOINTS} == set(load_policy()["actions"])


def test_unknown_action_is_denied():
    assert allowed_principals("does.not.exist") == frozenset()
    assert allowed_principals(None) == frozenset()


@pytest.mark.parametrize(
    "action,expected",
    [
        ("jobs.create", {"recruiter", "hr_admin"}),
        ("jobs.board", {"recruiter", "hiring_manager", "hr_admin"}),
        ("applications.bulk_status", {"recruiter", "hr_admin"}),
        ("applications.notes", {"recruiter", "hiring_manager", "hr_admin"}),
        ("applications.reveal", {"hr_admin"}),
        ("hira.message", {"candidate"}),
        ("fairness.check", {"hr_admin"}),
        ("interviews.plan_update", {"recruiter", "hr_admin"}),
        ("interviews.schedule_manual", {"recruiter", "hr_admin"}),
        ("interviewers.update", {"hr_admin"}),
        ("interviews.hold", {"candidate"}),
        ("interviews.confirm", {"candidate"}),
        ("interviews.reschedule", {"candidate"}),
        ("scorecards.submit", {"recruiter", "hiring_manager", "employee", "hr_admin"}),
        ("hira.briefing", {"recruiter", "hr_admin"}),
        ("hira.activity", {"recruiter", "hr_admin"}),
        ("offers.create", {"recruiter", "hr_admin"}),
        ("offers.approve", {"hiring_manager", "hr_admin"}),
        ("offers.reject", {"hiring_manager", "hr_admin"}),
        ("offers.send", {"recruiter", "hr_admin"}),
        ("offers.accept", {"candidate"}),
        ("offers.decline", {"candidate"}),
        ("offers.mine", {"candidate"}),
        ("users.create", {"hr_admin"}),
        ("users.update", {"hr_admin"}),
        ("org.manage", {"hr_admin"}),
        ("audit.list", {"hr_admin"}),
        ("outbox.list", {"hr_admin"}),
        ("applications.create", {"candidate"}),
        ("applications.list_mine", {"candidate"}),
        ("applications.status", {"recruiter", "hr_admin"}),
        ("auth.register", {"anonymous"}),
        ("onboarding.hire", {"recruiter", "hr_admin"}),
        ("leave.adjust", {"hr_admin"}),
        ("hr.config", {"hr_admin"}),
        ("hr.attention", {"hr_admin"}),
        *[
            (action, {"recruiter", "hiring_manager", "employee", "hr_admin"})
            for action in (
                "leave.apply",
                "leave.approve",
                "attendance.check",
                "attendance.approve",
                "team.calendar",
            )
        ],
    ],
)
def test_sensitive_actions_stay_narrow(action, expected):
    """Guards against someone loosening policy.json by accident."""
    assert allowed_principals(action) == frozenset(expected)


def test_policy_routes_and_dashboards_are_valid():
    policy = load_policy()
    assert policy["dashboards"] == {
        "candidate": "/candidate",
        "recruiter": "/recruiter",
        "hiring_manager": "/manager",
        "employee": "/employee",
        "hr_admin": "/admin",
    }
    for role, path in policy["dashboards"].items():
        assert role in policy["routes"][path]

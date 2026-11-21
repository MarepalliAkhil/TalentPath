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
def world(users, org, skills, application):
    job = application.job
    return {
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
        ("jobs.create", {"recruiter"}),
        ("users.create", {"hr_admin"}),
        ("users.update", {"hr_admin"}),
        ("org.manage", {"hr_admin"}),
        ("audit.list", {"hr_admin"}),
        ("outbox.list", {"hr_admin"}),
        ("applications.create", {"candidate"}),
        ("applications.list_mine", {"candidate"}),
        ("applications.status", {"recruiter", "hr_admin"}),
        ("auth.register", {"anonymous"}),
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

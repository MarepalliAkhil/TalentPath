"""Loads shared/policy.json, the single source of truth for permissions.

Anything not listed is denied. Tokens: "any" (everyone, anonymous included),
"authenticated" (every role), "anonymous" (signed-out visitors only),
"internal" (cron calls with the secret header).
"""

import json
from functools import lru_cache

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

ROLES = ("candidate", "recruiter", "manager", "employee", "hr", "admin")
ANONYMOUS = "anonymous"
INTERNAL = "internal"
PRINCIPALS = (*ROLES, ANONYMOUS)


def expand(tokens: list[str]) -> frozenset[str]:
    out: set[str] = set()
    for token in tokens:
        if token == "any":
            out.update(PRINCIPALS)
        elif token == "authenticated":
            out.update(ROLES)
        elif token in ROLES or token in (ANONYMOUS, INTERNAL):
            out.add(token)
        else:
            raise ImproperlyConfigured(f"Unknown policy token: {token!r}")
    if INTERNAL in out and len(out) > 1:
        raise ImproperlyConfigured("'internal' cannot be combined with other tokens.")
    return frozenset(out)


def validate(data: dict) -> dict:
    if data.get("default") != "deny":
        raise ImproperlyConfigured("Policy default must be 'deny'.")
    if tuple(data.get("roles", ())) != ROLES:
        raise ImproperlyConfigured("Policy roles do not match the code's roles.")
    actions = {}
    for name, spec in data.get("actions", {}).items():
        roles = spec.get("roles") or []
        if not roles:
            raise ImproperlyConfigured(f"Action {name} has no roles.")
        actions[name] = expand(roles)
    routes = {path: expand(roles) for path, roles in data.get("routes", {}).items()}
    dashboards = data.get("dashboards", {})
    if set(dashboards) != set(ROLES):
        raise ImproperlyConfigured("Every role needs a dashboard path.")
    return {"actions": actions, "routes": routes, "dashboards": dashboards, "raw": data}


@lru_cache(maxsize=1)
def load_policy() -> dict:
    with open(settings.POLICY_PATH, encoding="utf-8") as fh:
        return validate(json.load(fh))


def allowed_principals(action: str | None) -> frozenset[str]:
    if not action:
        return frozenset()
    return load_policy()["actions"].get(action, frozenset())


def dashboard_for(role: str) -> str:
    return load_policy()["dashboards"].get(role, "/")

import hmac

from django.conf import settings
from rest_framework.permissions import BasePermission

from .policy import ANONYMOUS, INTERNAL, allowed_principals


def resolve_action(view, method: str) -> str | None:
    """Policy action for this view and HTTP method; None means deny."""
    actions = getattr(view, "policy_actions", None)
    if actions:
        if method in ("HEAD", "OPTIONS"):
            method = "GET"
        return actions.get(method)
    return getattr(view, "policy_action", None)


def internal_secret_ok(request) -> bool:
    supplied = request.headers.get("X-Internal-Secret", "")
    expected = settings.INTERNAL_TICK_SECRET
    return bool(supplied) and hmac.compare_digest(supplied.encode(), expected.encode())


class PolicyPermission(BasePermission):
    """Deny by default; allow only what shared/policy.json grants."""

    message = "Your role is not allowed to perform this action."

    def has_permission(self, request, view) -> bool:
        allowed = allowed_principals(resolve_action(view, request.method))
        if not allowed:
            return False
        if INTERNAL in allowed:
            return internal_secret_ok(request)
        user = getattr(request, "user", None)
        principal = user.role if user is not None and user.is_authenticated else ANONYMOUS
        return principal in allowed

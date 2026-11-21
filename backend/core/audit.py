from rest_framework.throttling import BaseThrottle

from .models import AuditLog


def client_ip(request) -> str | None:
    if request is None:
        return None
    ip = BaseThrottle().get_ident(request)
    return ip or None


def audit(request, action: str, *, actor=None, target=None, **meta) -> AuditLog:
    """Record a sensitive action. Never put personal data in meta."""
    if actor is None and request is not None:
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            actor = user
    target_type = target_id = ""
    if target is not None:
        target_type = target._meta.model_name
        target_id = str(target.pk)
    return AuditLog.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        ip_address=client_ip(request),
        meta=meta,
    )

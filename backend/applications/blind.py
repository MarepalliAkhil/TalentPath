"""Blind screening rules."""

from django.utils import timezone

from core.audit import audit

from .models import ApplicationStatus as S
from .redact import redact

STAGE_ORDER = {S.APPLIED: 0, S.SCREENING: 1, S.INTERVIEW: 2, S.OFFER: 3, S.HIRED: 4}


def is_blind(application) -> bool:
    return bool(application.job.blind_screening) and application.identity_revealed_at is None


def known_values(application) -> dict:
    user = application.candidate
    profile = getattr(user, "profile", None)
    return {
        "full_name": user.full_name,
        "email": user.email,
        "phone": profile.phone if profile else "",
        "address": profile.address if profile else "",
        "city": profile.location_text if profile else "",
    }


def redacted_text(application, text: str) -> str:
    return redact(text, known_values(application))


def reveal(application, *, actor, reason: str, request=None, automatic: bool) -> None:
    application.identity_revealed_at = timezone.now()
    application.revealed_by = actor
    application.reveal_reason = reason[:300]
    application.save(update_fields=["identity_revealed_at", "revealed_by", "reveal_reason", "updated_at"])
    audit(
        request,
        "applications.identity_revealed",
        actor=actor,
        target=application,
        automatic=automatic,
        stage=application.status,
        reason=reason[:300],
    )


def maybe_auto_reveal(application, *, actor, request=None) -> bool:
    job = application.job
    if not is_blind(application):
        return False
    if STAGE_ORDER.get(application.status, -1) >= STAGE_ORDER[job.reveal_stage]:
        reveal(
            application,
            actor=actor,
            request=request,
            automatic=True,
            reason=f"Reached the {job.get_reveal_stage_display()} stage",
        )
        return True
    return False

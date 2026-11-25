import logging
import secrets

from asgiref.sync import async_to_sync
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .models import EmailOutbox, Notification

log = logging.getLogger(__name__)


def queue_email(
    *,
    to_email: str,
    subject: str,
    body: str,
    kind: str,
    user=None,
    attachment: tuple | None = None,
    bell: bool = True,
) -> EmailOutbox:
    """Write an email to the outbox (branded HTML plus plain text) and hand it to the
    delivery service (D-86), which sends it after the transaction commits.

    `attachment` is an optional (filename, content_type, text) tuple, e.g. an .ics invite.
    `bell`: also show it under the person's bell (without any link, which may be single-use).
    """
    from .delivery import SAFETY_NET, schedule
    from .templates import render

    name, ctype, content = attachment or ("", "", "")
    plain, html_body = render(kind=kind, subject=subject, body=body)
    email = EmailOutbox.objects.create(
        user=user,
        to_email=to_email,
        subject=subject[:200],
        body=plain,
        html_body=html_body,
        kind=kind,
        attachment_name=name[:120],
        attachment_type=ctype[:60],
        attachment=content,
        next_attempt_at=timezone.now() + SAFETY_NET,
    )
    if bell and user is not None:
        Notification.objects.create(
            user=user, kind=kind, title=subject[:160], body=f"We emailed {to_email} about this."
        )
    schedule(email)
    return email


def wants_email(user, kind: str) -> bool:
    """Notification preferences: account emails always go; other categories can be switched off."""
    from .templates import category_for

    category = category_for(kind)
    if category == "account":
        return True
    from accounts.models import Profile

    prefs = Profile.objects.filter(user_id=user.pk).values_list("notification_prefs", flat=True).first() or {}
    return prefs.get(category, True) is not False


def user_group(user_id) -> str:
    return f"user_{str(user_id).replace('-', '')}"


def push_realtime(user_id, payload: dict) -> None:
    try:
        from channels.layers import get_channel_layer

        layer = get_channel_layer()
        if layer is not None:
            async_to_sync(layer.group_send)(user_group(user_id), {"type": "notify", "payload": payload})
    except Exception:  # realtime is best effort; polling still works
        log.debug("Realtime push failed", exc_info=True)


def notify(
    user,
    *,
    kind: str,
    title: str,
    body: str = "",
    link: str = "",
    email: bool = True,
    email_link: str = "",
    attachment: tuple | None = None,
):
    """Bell notification plus (by default) a simulated email.

    `email_link` overrides the link in the email only (for example a single-use
    scheduling link that must not be stored in the in-app notification).
    """
    note = Notification.objects.create(user=user, kind=kind, title=title[:160], body=body, link=link[:200])
    if email and wants_email(user, kind):
        queue_email(
            to_email=user.email,
            user=user,
            kind=kind,
            subject=title,
            body=f"Hi {user.full_name},\n\n{body}\n\n{settings.SITE_URL}{email_link or link}",
            attachment=attachment,
            bell=False,
        )
    push_realtime(user.pk, {"id": str(note.id), "title": note.title, "kind": kind})
    return note


def issue_ws_ticket(user) -> str:
    ticket = secrets.token_urlsafe(32)
    cache.set(f"ws-ticket:{ticket}", str(user.pk), settings.WS_TICKET_TTL_SECONDS)
    return ticket


def redeem_ws_ticket(ticket: str) -> str | None:
    """Single use: the ticket is deleted the first time it is redeemed."""
    if not ticket:
        return None
    key = f"ws-ticket:{ticket}"
    user_id = cache.get(key)
    if user_id is not None:
        cache.delete(key)
    return user_id

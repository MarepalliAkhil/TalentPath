"""Email delivery (D-86): one service, three providers chosen by EMAIL_PROVIDER.

- "console" (default, and in tests): nothing leaves the machine; one log line per email
  (masked recipient, kind, subject; never the body, which can hold sign-in links).
- "smtp": Django's SMTP backend, for local use with a Gmail App Password
  (EMAIL_HOST_USER / EMAIL_HOST_PASSWORD).
- "api": an HTTPS email API (Brevo or Resend, EMAIL_API_PROVIDER + EMAIL_API_KEY), for
  Render, whose free plan blocks outgoing SMTP ports.

Every email is first written to the outbox (the in-app copy and the send log). Real
providers then send it after the transaction commits, in a background thread so a request
never waits for a mail server. Safety before anything leaves:
- reserved demo domains (.example, .test, .invalid, .localhost) are never sent;
- EMAIL_ALLOWLIST, when set, limits real sends to the listed addresses (or @domains);
- per recipient per hour, everyone per hour and per day caps;
failures retry with backoff (1, 5, 15, 60 minutes) and are picked up again by the tick.
Credentials only ever come from the environment and are scrubbed from any stored error.
"""

import json
import logging
import re
import threading
import urllib.error
import urllib.request
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db import close_old_connections, connection, transaction
from django.utils import timezone

from .models import EmailOutbox, EmailStatus

log = logging.getLogger("talentpath.email")

PROVIDERS = ("console", "smtp", "api")
API_PROVIDERS = ("brevo", "resend")
RESERVED_SUFFIXES = (".example", ".test", ".invalid", ".localhost")
BACKOFF_MINUTES = (1, 5, 15, 60)
LEASE = timedelta(minutes=2)
SAFETY_NET = timedelta(minutes=10)  # if a send thread dies, the tick picks the email up after this
API_URLS = {
    "brevo": "https://api.brevo.com/v3/smtp/email",
    "resend": "https://api.resend.com/emails",
}


class EmailConfigError(RuntimeError):
    pass


def provider() -> str:
    name = (getattr(settings, "EMAIL_PROVIDER", "console") or "console").strip().lower()
    if name not in PROVIDERS:
        raise EmailConfigError(f"EMAIL_PROVIDER must be one of {', '.join(PROVIDERS)}.")
    return name


def mask(address: str) -> str:
    local, _, domain = (address or "").partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"


def _secrets() -> list[str]:
    values = [getattr(settings, "EMAIL_HOST_PASSWORD", ""), getattr(settings, "EMAIL_API_KEY", "")]
    return [v for v in values if v and len(v) >= 4]


def scrub(text: str) -> str:
    """Remove credentials (and anything that looks like an API key or bearer token) from text."""
    out = str(text or "")
    for secret in _secrets():
        out = out.replace(secret, "***")
    out = re.sub(r"(?i)(bearer|api[-_ ]?key|password)[\s:=\"']+\S+", r"\1 ***", out)
    out = re.sub(r"\b(xkeysib|re)_[A-Za-z0-9_\-]{8,}", "***", out)
    return out[:300]


def allowlist() -> list[str]:
    raw = getattr(settings, "EMAIL_ALLOWLIST", "") or ""
    return [item.strip().lower() for item in raw.split(",") if item.strip()]


def _allowed(address: str) -> bool:
    entries = allowlist()
    if not entries:
        return True
    address = address.lower()
    domain = "@" + address.partition("@")[2]
    return any(entry == address or (entry.startswith("@") and entry == domain) for entry in entries)


def hold_reason(email: EmailOutbox, now=None) -> str:
    """Why a real provider must not send this email now ("" means it may go)."""
    now = now or timezone.now()
    address = email.to_email.lower()
    if address.endswith(RESERVED_SUFFIXES):
        return "Reserved demo address: never sent"
    if not _allowed(address):
        return "Not on EMAIL_ALLOWLIST"
    real = EmailOutbox.objects.filter(status=EmailStatus.SENT).exclude(provider__in=("console", "simulated"))
    hour_ago, day_ago = now - timedelta(hours=1), now - timedelta(days=1)
    if (
        real.filter(to_email__iexact=address, sent_at__gte=hour_ago).count()
        >= settings.EMAIL_MAX_PER_RECIPIENT_PER_HOUR
    ):
        return "Limit reached for this recipient this hour"
    if real.filter(sent_at__gte=hour_ago).count() >= settings.EMAIL_MAX_PER_HOUR:
        return "Hourly email limit reached"
    if real.filter(sent_at__gte=day_ago).count() >= settings.EMAIL_DAILY_CAP:
        return "Daily email cap reached"
    return ""


# ---------------------------------------------------------------- providers
def _from_header() -> tuple[str, str]:
    return settings.EMAIL_FROM_NAME, settings.DEFAULT_FROM_EMAIL


def send_smtp(email: EmailOutbox) -> None:
    if not (settings.EMAIL_HOST_USER and settings.EMAIL_HOST_PASSWORD):
        raise EmailConfigError("SMTP needs EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in the environment.")
    name, address = _from_header()
    conn = get_connection(
        "django.core.mail.backends.smtp.EmailBackend",
        host=settings.EMAIL_HOST,
        port=settings.EMAIL_PORT,
        username=settings.EMAIL_HOST_USER,
        password=settings.EMAIL_HOST_PASSWORD,
        use_tls=settings.EMAIL_USE_TLS,
        timeout=settings.EMAIL_TIMEOUT,
    )
    message = EmailMultiAlternatives(
        subject=email.subject,
        body=email.body,
        from_email=f"{name} <{address}>",
        to=[email.to_email],
        connection=conn,
    )
    if email.html_body:
        message.attach_alternative(email.html_body, "text/html")
    if email.attachment_name:
        message.attach(email.attachment_name, email.attachment, email.attachment_type or "text/plain")
    message.send(fail_silently=False)


def _api_payload(email: EmailOutbox, api: str) -> dict:
    name, address = _from_header()
    if api == "brevo":
        payload = {
            "sender": {"name": name, "email": address},
            "to": [{"email": email.to_email}],
            "subject": email.subject,
            "textContent": email.body,
            "htmlContent": email.html_body or None,
        }
        if email.attachment_name:
            import base64

            payload["attachment"] = [
                {
                    "name": email.attachment_name,
                    "content": base64.b64encode(email.attachment.encode()).decode(),
                }
            ]
        return {k: v for k, v in payload.items() if v is not None}
    payload = {
        "from": f"{name} <{address}>",
        "to": [email.to_email],
        "subject": email.subject,
        "text": email.body,
        "html": email.html_body or None,
    }
    if email.attachment_name:
        import base64

        payload["attachments"] = [
            {
                "filename": email.attachment_name,
                "content": base64.b64encode(email.attachment.encode()).decode(),
            }
        ]
    return {k: v for k, v in payload.items() if v is not None}


def send_api(email: EmailOutbox) -> None:
    api = (settings.EMAIL_API_PROVIDER or "").strip().lower()
    if api not in API_PROVIDERS or not settings.EMAIL_API_KEY:
        raise EmailConfigError(
            "The API provider needs EMAIL_API_PROVIDER (brevo or resend) and EMAIL_API_KEY."
        )
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if api == "brevo":
        headers["api-key"] = settings.EMAIL_API_KEY
    else:
        headers["Authorization"] = f"Bearer {settings.EMAIL_API_KEY}"
    request = urllib.request.Request(  # noqa: S310 - fixed https URL from API_URLS
        API_URLS[api], data=json.dumps(_api_payload(email, api)).encode(), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.EMAIL_TIMEOUT) as response:  # noqa: S310 - fixed https URL
            if response.status >= 300:
                raise RuntimeError(f"Email API answered {response.status}")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Email API answered {exc.code}") from None


def _sender(name: str):
    # Looked up at call time (not a dict built at import) so tests can replace a provider.
    return {"smtp": send_smtp, "api": send_api}[name]


# ---------------------------------------------------------------- delivery
def _claim(email_id, from_tick: bool, now) -> EmailOutbox | None:
    """Take a short lease so the send thread and the tick never send the same email twice.
    The first send right after writing goes at once; the tick only takes emails that are due."""
    with transaction.atomic():
        email = EmailOutbox.objects.select_for_update().filter(pk=email_id, status=EmailStatus.QUEUED).first()
        if email is None or (from_tick and email.next_attempt_at and email.next_attempt_at > now):
            return None
        email.next_attempt_at = now + LEASE
        email.save(update_fields=["next_attempt_at"])
        return email


def deliver(email_id, *, from_tick: bool = False, now=None) -> str:
    """Send one queued email with the configured provider. Returns the new status ("" if
    someone else is already sending it or it is not due)."""
    name = provider()
    now = now or timezone.now()
    email = _claim(email_id, from_tick, now)
    if email is None:
        return ""
    if name == "console":
        log.info(
            "email %s kind=%s to=%s subject=%r (console: not sent)",
            email.pk,
            email.kind,
            mask(email.to_email),
            email.subject,
        )
        _finish(email, EmailStatus.SENT, provider="console", sent_at=now)
        return EmailStatus.SENT
    reason = hold_reason(email, now)
    if reason:
        log.info("email %s held: %s", email.pk, reason)
        _finish(email, EmailStatus.HELD, provider=name, hold_reason=reason)
        return EmailStatus.HELD
    try:
        _sender(name)(email)
    except Exception as exc:  # any provider error: record it (scrubbed) and back off
        attempts = email.attempts + 1
        error = scrub(f"{type(exc).__name__}: {exc}")
        log.warning("email %s attempt %s failed: %s", email.pk, attempts, error)
        if attempts >= settings.EMAIL_MAX_ATTEMPTS or isinstance(exc, EmailConfigError):
            _finish(email, EmailStatus.FAILED, provider=name, attempts=attempts, last_error=error)
            return EmailStatus.FAILED
        delay = BACKOFF_MINUTES[min(attempts - 1, len(BACKOFF_MINUTES) - 1)]
        _finish(
            email,
            EmailStatus.QUEUED,
            provider=name,
            attempts=attempts,
            last_error=error,
            next_attempt_at=now + timedelta(minutes=delay),
        )
        return EmailStatus.QUEUED
    log.info("email %s kind=%s sent to %s via %s", email.pk, email.kind, mask(email.to_email), name)
    _finish(email, EmailStatus.SENT, provider=name, attempts=email.attempts + 1, sent_at=now, last_error="")
    return EmailStatus.SENT


def _finish(email: EmailOutbox, status: str, **fields) -> None:
    fields.setdefault("next_attempt_at", None)
    EmailOutbox.objects.filter(pk=email.pk).update(status=status, **fields)


def _deliver_in_thread(email_id) -> None:
    def run():
        try:
            deliver(email_id)
        except Exception:  # the tick retries anything left queued
            log.exception("email %s delivery thread failed", email_id)
        finally:
            close_old_connections()
            connection.close()

    threading.Thread(target=run, name=f"email-{email_id}", daemon=True).start()


def schedule(email: EmailOutbox) -> None:
    """Called right after an email is written to the outbox."""
    name = provider()
    if name == "console":
        transaction.on_commit(lambda: deliver(email.pk))
    else:
        transaction.on_commit(lambda: _deliver_in_thread(email.pk))


def retry_due(now=None, limit: int = 50) -> int:
    """Tick: send queued emails whose next attempt is due (failed attempts and lost threads)."""
    now = now or timezone.now()
    due = list(
        EmailOutbox.objects.filter(status=EmailStatus.QUEUED, next_attempt_at__lte=now)
        .order_by("next_attempt_at")
        .values_list("pk", flat=True)[:limit]
    )
    return sum(1 for pk in due if deliver(pk, from_tick=True, now=now))


def status_counts() -> dict:
    from django.db.models import Count

    rows = EmailOutbox.objects.values("status").annotate(n=Count("pk"))
    return {row["status"]: row["n"] for row in rows}

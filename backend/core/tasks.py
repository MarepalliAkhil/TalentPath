"""Work triggered by cron-job.org through POST /api/internal/tick and /nightly.

Week 3 adds interview reminders (tick) here; keep every task idempotent and
fast, because the free Render instance may be cold-starting.
"""

from datetime import timedelta

from django.utils import timezone


def run_tick() -> dict:
    return {"ran_at": timezone.now().isoformat(), "tasks": {}}


def run_nightly() -> dict:
    from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

    from notifications.models import EmailOutbox

    now = timezone.now()
    expired, _ = OutstandingToken.objects.filter(expires_at__lt=now).delete()
    old_mail, _ = EmailOutbox.objects.filter(created_at__lt=now - timedelta(days=30)).delete()
    return {
        "ran_at": now.isoformat(),
        "tasks": {"expired_tokens_deleted": expired, "old_outbox_deleted": old_mail},
    }

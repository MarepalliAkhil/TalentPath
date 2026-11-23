"""Work triggered by cron-job.org through POST /api/internal/tick and /nightly.

Tick (every few minutes): HIRA's interview work (expired holds, finished
interviews, 24 h / 1 h reminders, overdue scorecards), offer expiry, leave
delegation and escalation. Nightly: token and outbox clean-up, monthly leave
accrual, year-end carry-forward and missing check-outs. Every task is
idempotent and fast, because the free Render instance may be cold-starting.
"""

from datetime import timedelta

from django.utils import timezone


def run_tick(now=None) -> dict:
    from interviews.coordinator import tick as interview_tick
    from offers.services import expire_offers

    now = now or timezone.now()
    tasks = interview_tick(now)
    tasks["offers_expired"] = expire_offers(now)
    from hr import leave

    tasks["leave_delegated"] = leave.refresh_delegations(now)
    tasks["leave_escalated"] = leave.escalate_due(now)
    return {"ran_at": now.isoformat(), "tasks": tasks}


def run_nightly(now=None) -> dict:
    from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

    from hr import attendance, leave
    from interviews.timeutil import today_ist
    from notifications.models import EmailOutbox

    now = now or timezone.now()
    today = today_ist(now)
    expired, _ = OutstandingToken.objects.filter(expires_at__lt=now).delete()
    old_mail, _ = EmailOutbox.objects.filter(created_at__lt=now - timedelta(days=30)).delete()
    year_end = leave.run_year_end(today)
    from core.demo import reset_demo_data

    demo = reset_demo_data(now)  # only when DEMO_MODE is on; only *.example demo data
    return {
        "ran_at": now.isoformat(),
        "tasks": {
            "demo_reset": not demo.get("skipped", True),
            "expired_tokens_deleted": expired,
            "old_outbox_deleted": old_mail,
            "leave_carried": year_end["carried"],
            "leave_lapsed": year_end["lapsed"],
            "leave_credited": leave.run_accruals(today),
            "missing_checkouts": attendance.mark_missing_checkouts(now),
        },
    }

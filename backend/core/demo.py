"""Demo mode (week 4A). Off by default (`DEMO_MODE=false`).

When it is on:
- the login page offers "Try as …" buttons that sign in to the seeded demo accounts;
- every page shows "Demo data, resets nightly";
- demo accounts (the seeded *.example addresses) cannot change their password, invite or
  edit staff, move applications in bulk or delete records;
- uploads are limited in size and count for everyone;
- the nightly job rebuilds the demo data (seed --reset), touching only demo records.
"""

from io import StringIO

from django.conf import settings
from django.core.management import call_command
from rest_framework.exceptions import PermissionDenied, ValidationError

# The seed creates staff at demo.example and synthetic candidates at candidates.example.
DEMO_DOMAINS = ("@demo.example", "@candidates.example")
DEMO_SUFFIX = ".example"  # what seed --reset removes (see seeding)
DEMO_UPLOAD_MAX_BYTES = 1024 * 1024
DEMO_UPLOADS_PER_USER = 10

# (role, button label, email) — the six seeded logins.
DEMO_ACCOUNTS = [
    ("candidate", "Candidate", "candidate@demo.example"),
    ("recruiter", "Recruiter", "recruiter@demo.example"),
    ("manager", "Manager", "manager@demo.example"),
    ("employee", "Employee", "employee@demo.example"),
    ("hr", "HR", "hr@demo.example"),
    ("admin", "Admin", "admin@demo.example"),
]


def demo_mode() -> bool:
    return bool(getattr(settings, "DEMO_MODE", False))


def is_demo_email(email: str) -> bool:
    return (email or "").lower().endswith(DEMO_DOMAINS)


def is_demo_account(user) -> bool:
    return (
        demo_mode() and bool(user and getattr(user, "is_authenticated", False)) and is_demo_email(user.email)
    )


def deny_demo(user, what: str) -> None:
    """Raise 403 when a demo account tries something that would spoil the demo for others."""
    if is_demo_account(user):
        raise PermissionDenied(f"Demo accounts cannot {what}. Everything resets nightly.")


def check_demo_upload(user, size: int, field: str = "resume") -> None:
    """In demo mode every upload is limited to 1 MB and 10 files per person."""
    if not demo_mode():
        return
    if size > DEMO_UPLOAD_MAX_BYTES:
        raise ValidationError({field: "In the demo, files must be 1 MB or smaller."})
    from files.models import StoredFile

    if user is not None and StoredFile.objects.filter(owner=user).count() >= DEMO_UPLOADS_PER_USER:
        raise ValidationError(
            {field: f"In the demo, each person can upload up to {DEMO_UPLOADS_PER_USER} files."}
        )


def demo_config() -> dict:
    on = demo_mode()
    # Prompt 1 (D-87): no banner anywhere; the "Try as" buttons live only on For recruiters.
    return {
        "demo_mode": on,
        "accounts": [{"role": r, "label": label} for r, label, _ in DEMO_ACCOUNTS] if on else [],
        "upload_limit_bytes": DEMO_UPLOAD_MAX_BYTES if on else None,
    }


def demo_account_for(role: str):
    from accounts.models import User

    email = next((e for r, _, e in DEMO_ACCOUNTS if r == role), None)
    if email is None:
        return None
    return User.objects.filter(email=email, is_active=True).first()


def reset_demo_data(now=None) -> dict:
    """Rebuild the demo data from scratch. Only *.example users, their jobs and the records that
    hang off them are removed (see `seed --reset`); every other account and its data stay."""
    from core.audit import audit

    if not demo_mode():
        return {"skipped": True}
    call_command("seed", reset=True, stdout=StringIO())
    from accounts.models import User

    demo_users = User.objects.filter(email__endswith=DEMO_SUFFIX).count()
    audit(None, "demo.reset", demo_users=demo_users)
    return {"skipped": False, "demo_users": demo_users}


# ---------------------------------------------------------------- background reset (week 4B)
_reset_lock = __import__("threading").Lock()


def start_demo_reset_in_background() -> str:
    """Start the demo reset in a background thread and return at once.

    cron-job.org gives up after 30 seconds and a full reseed on the free tier can take longer,
    so the nightly endpoint answers immediately ("started") while the single Daphne process
    finishes the work. A lock stops two resets from overlapping ("running").
    """
    import threading

    from django.db import connection

    if not demo_mode():
        return "skipped"
    if not _reset_lock.acquire(blocking=False):
        return "running"

    def work():
        try:
            reset_demo_data()
        finally:
            connection.close()
            _reset_lock.release()

    threading.Thread(target=work, name="demo-reset", daemon=True).start()
    return "started"

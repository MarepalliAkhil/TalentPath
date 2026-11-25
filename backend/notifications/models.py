import uuid

from django.conf import settings
from django.db import models


class Notification(models.Model):
    """In-app notification shown under the bell."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=40)
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True, default="")
    link = models.CharField(max_length=200, blank=True, default="")
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]


class EmailStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    SENT = "sent", "Sent"
    HELD = "held", "Held (not sent)"
    FAILED = "failed", "Failed"


class EmailOutbox(models.Model):
    """Every email the app writes (D-86). The outbox is also the send log: the delivery
    provider, attempts, the last (redacted) error and why a message was held."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="emails",
    )
    to_email = models.EmailField(max_length=254, db_index=True)
    kind = models.CharField(max_length=40)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    # Optional single text attachment (for example an .ics calendar invite).
    attachment_name = models.CharField(max_length=120, blank=True, default="")
    attachment_type = models.CharField(max_length=60, blank=True, default="")
    attachment = models.TextField(blank=True, default="")
    html_body = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=10, choices=EmailStatus.choices, default=EmailStatus.QUEUED, db_index=True
    )
    provider = models.CharField(max_length=20, blank=True, default="")
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.CharField(max_length=300, blank=True, default="")
    hold_reason = models.CharField(max_length=160, blank=True, default="")
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

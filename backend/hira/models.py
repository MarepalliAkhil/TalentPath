import uuid

from django.db import models
from django.utils import timezone


class KnowledgeEntry(models.Model):
    """A question and answer Ask HIRA can retrieve (BM25 over question, keywords and answer)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.SlugField(max_length=60, unique=True)
    question = models.CharField(max_length=200)
    keywords = models.CharField(max_length=300, blank=True, default="")
    answer = models.TextField()
    link = models.CharField(max_length=200, blank=True, default="")
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["key"]

    def __str__(self) -> str:
        return self.question


class HiraAction(models.TextChoices):
    SLOTS_PROPOSED = "slots_proposed", "Proposed interview slots"
    INTERVIEW_SCHEDULED = "interview_scheduled", "Scheduled an interview"
    RESCHEDULE_HANDLED = "reschedule_handled", "Handled a reschedule"
    INTERVIEWER_REPLACED = "interviewer_replaced", "Found a replacement interviewer"
    REMINDER_SENT = "reminder_sent", "Sent interview reminders"
    SCORECARD_CHASED = "scorecard_chased", "Chased an overdue scorecard"
    NEXT_ROUND = "next_round", "Started the next interview round"
    HOLD_EXPIRED = "hold_expired", "Released an expired slot hold"
    NO_SLOTS = "no_slots", "Could not find free slots"
    REPLACEMENT_FAILED = "replacement_failed", "Could not find a replacement interviewer"
    SCORECARD_OVERDUE = "scorecard_overdue", "Flagged feedback overdue for 48 hours"
    RESCHEDULE_LIMIT = "reschedule_limit", "Candidate reached the reschedule limit"
    MANUAL_SCHEDULED = "manual_scheduled", "Recorded a manual schedule"


# Actions that put an item on a person's "Needs you" list while it stays unresolved.
NEEDS_YOU_ACTIONS = (
    HiraAction.NO_SLOTS,
    HiraAction.REPLACEMENT_FAILED,
    HiraAction.SCORECARD_OVERDUE,
    HiraAction.RESCHEDULE_LIMIT,
)


class AppendOnlyError(Exception):
    pass


class HiraActivity(models.Model):
    """Append-only log of everything HIRA does (also mirrored to the audit log).

    Rows are never edited: save() refuses updates and delete() is refused. Only the
    demo `seed --reset` removes rows, with a queryset delete of demo data.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    action = models.CharField(max_length=30, choices=HiraAction.choices, db_index=True)
    job = models.ForeignKey("jobs.Job", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    application = models.ForeignKey(
        "applications.Application", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    interview = models.ForeignKey(
        "interviews.Interview", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    # For a per-interviewer item (overdue scorecard), who it is about. Never shown to candidates.
    subject_user = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reason_code = models.CharField(max_length=40, blank=True, default="")
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    needs_you = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise AppendOnlyError("HIRA activity is append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AppendOnlyError("HIRA activity is append-only.")


class BriefingState(models.Model):
    """When a user last saw HIRA's login briefing ("while you were away" starts here)."""

    user = models.OneToOneField("accounts.User", on_delete=models.CASCADE, primary_key=True, related_name="+")
    last_seen_at = models.DateTimeField()

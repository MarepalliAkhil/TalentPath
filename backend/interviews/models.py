"""Interview plans, interviewer availability, interviews, slots, time claims and scorecards.

All times are stored in UTC and shown in Asia/Kolkata (see timeutil.py).
"""

import uuid

from django.conf import settings
from django.db import models

from core.fields import EncryptedTextField


class Mode(models.TextChoices):
    VIDEO = "video", "Video call"
    IN_PERSON = "in_person", "In person"
    PHONE = "phone", "Phone"


def default_working_hours() -> dict:
    """Monday to Friday, 10:00 to 18:00 IST. Keys are ISO weekdays as strings (1 = Monday)."""
    return {str(day): ["10:00", "18:00"] for day in range(1, 6)}


class InterviewerProfile(models.Model):
    """A staff member who can interview: skills for pools, and weekly working hours (IST)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="interviewer_profile"
    )
    skills = models.ManyToManyField("org.Skill", blank=True, related_name="interviewers")
    working_hours = models.JSONField(default=default_working_hours)
    active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Interviewer {self.user_id}"


class BlockedTime(models.Model):
    """Time an interviewer is not available (leave, focus time, other meetings)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocked_times")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    reason = models.CharField(max_length=120, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["starts_at"]
        indexes = [models.Index(fields=["user", "starts_at"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")), name="blocked_time_positive"
            )
        ]


class InterviewPlan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.OneToOneField("jobs.Job", on_delete=models.CASCADE, related_name="interview_plan")
    # "Let HIRA schedule": when off, recruiters schedule by hand (same clash checks).
    hira_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Plan for {self.job_id}"


class InterviewRound(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(InterviewPlan, on_delete=models.CASCADE, related_name="rounds")
    order = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=60)
    duration_minutes = models.PositiveSmallIntegerField(default=60)
    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.VIDEO)
    interviewers_needed = models.PositiveSmallIntegerField(default=1)  # 1, or a panel
    pool = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="interview_pools")

    class Meta:
        ordering = ["plan", "order"]
        constraints = [models.UniqueConstraint(fields=["plan", "order"], name="uniq_round_order")]

    def __str__(self) -> str:
        return f"{self.order}. {self.name}"


class InterviewStatus(models.TextChoices):
    PENDING = "pending", "Waiting for the candidate to pick a slot"
    SCHEDULED = "scheduled", "Scheduled"
    COMPLETED = "completed", "Completed"
    NO_SHOW = "no_show", "Candidate did not join"
    CANCELLED = "cancelled", "Cancelled"


ACTIVE_INTERVIEW = (InterviewStatus.PENDING, InterviewStatus.SCHEDULED)


class Attention(models.TextChoices):
    """Why an interview needs a person (shown in HIRA's "Needs you" list)."""

    NONE = "", "None"
    NO_SLOTS = "no_slots", "No common free slots found"
    REPLACEMENT_FAILED = "replacement_failed", "No replacement interviewer was free"
    RESCHEDULE_LIMIT = "reschedule_limit", "Candidate reached the reschedule limit"


class Interview(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        "applications.Application", on_delete=models.CASCADE, related_name="interviews"
    )
    round = models.ForeignKey(InterviewRound, on_delete=models.PROTECT, related_name="interviews")
    status = models.CharField(
        max_length=12, choices=InterviewStatus.choices, default=InterviewStatus.PENDING, db_index=True
    )
    attention = models.CharField(max_length=24, choices=Attention.choices, blank=True, default="")
    starts_at = models.DateTimeField(null=True, blank=True, db_index=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    mode = models.CharField(max_length=10, choices=Mode.choices, default=Mode.VIDEO)
    meeting_link = models.CharField(max_length=200, blank=True, default="")
    scheduled_by = models.CharField(max_length=10, blank=True, default="")  # "hira" or "manual"
    reschedule_count = models.PositiveSmallIntegerField(default=0)
    reminder_24h_sent_at = models.DateTimeField(null=True, blank=True)
    reminder_1h_sent_at = models.DateTimeField(null=True, blank=True)
    scorecard_due_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["round__order", "created_at"]
        constraints = [
            # One live interview per round per application.
            models.UniqueConstraint(
                fields=["application", "round"],
                condition=models.Q(status__in=["pending", "scheduled"]),
                name="uniq_active_interview_per_round",
            )
        ]

    def __str__(self) -> str:
        return f"{self.round} for {self.application_id}"


class AssignmentStatus(models.TextChoices):
    ASSIGNED = "assigned", "Assigned"
    DECLINED = "declined", "Declined"


class InterviewAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    interview = models.ForeignKey(Interview, on_delete=models.CASCADE, related_name="assignments")
    interviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="interview_assignments"
    )
    status = models.CharField(
        max_length=10, choices=AssignmentStatus.choices, default=AssignmentStatus.ASSIGNED
    )
    decline_reason = models.CharField(max_length=200, blank=True, default="")
    chased_at = models.DateTimeField(null=True, blank=True)
    overdue_flagged_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["interview", "interviewer"], name="uniq_assignment"),
        ]


class SlotStatus(models.TextChoices):
    OPEN = "open", "Offered"
    HELD = "held", "Held while the candidate confirms"
    TAKEN = "taken", "Booked"
    WITHDRAWN = "withdrawn", "No longer offered"


class SlotOffer(models.Model):
    """A slot HIRA (or a recruiter) offered for one interview. Offering does not block time; holding does."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    interview = models.ForeignKey(Interview, on_delete=models.CASCADE, related_name="slots")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    interviewer_ids = models.JSONField(default=list)
    status = models.CharField(max_length=10, choices=SlotStatus.choices, default=SlotStatus.OPEN)
    held_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["starts_at"]


class ClaimKind(models.TextChoices):
    HOLD = "hold", "Hold"
    INTERVIEW = "interview", "Interview"


class TimeClaim(models.Model):
    """Busy time for one person (interviewer or candidate).

    Active claims may never overlap for the same person. On PostgreSQL this is
    enforced by an exclusion constraint (btree_gist), added in migration 0002;
    the service layer also checks inside a transaction with row locks.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="time_claims")
    interview = models.ForeignKey(Interview, on_delete=models.CASCADE, related_name="claims")
    slot = models.ForeignKey(
        SlotOffer, null=True, blank=True, on_delete=models.SET_NULL, related_name="claims"
    )
    kind = models.CharField(max_length=10, choices=ClaimKind.choices)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    expires_at = models.DateTimeField(null=True, blank=True)  # holds only
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["person", "active", "starts_at"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")), name="claim_positive"
            )
        ]


class LinkToken(models.Model):
    """Single-use, expiring link a candidate can use from the email to pick a slot."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    interview = models.ForeignKey(Interview, on_delete=models.CASCADE, related_name="link_tokens")
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Recommendation(models.TextChoices):
    STRONG_NO = "strong_no", "Strong no"
    NO = "no", "No"
    YES = "yes", "Yes"
    STRONG_YES = "strong_yes", "Strong yes"


POSITIVE = (Recommendation.YES, Recommendation.STRONG_YES)


class Scorecard(models.Model):
    """One interviewer's independent feedback for one interview. Comments are encrypted."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    interview = models.ForeignKey(Interview, on_delete=models.CASCADE, related_name="scorecards")
    interviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="scorecards"
    )
    ratings = models.JSONField(default=dict)  # criterion key -> 1..5
    criteria = models.JSONField(default=list)  # [{key, label}] snapshot of the template
    comments = EncryptedTextField(blank=True, default="")  # JSON: criterion key -> comment
    summary = EncryptedTextField(blank=True, default="")
    recommendation = models.CharField(max_length=12, choices=Recommendation.choices)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["submitted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["interview", "interviewer"], name="uniq_scorecard_per_interviewer"
            )
        ]

import uuid

from django.conf import settings
from django.db import models

from core.fields import EncryptedTextField


class ApplicationStatus(models.TextChoices):
    APPLIED = "applied", "Applied"
    SCREENING = "screening", "Screening"
    INTERVIEW = "interview", "Interview"
    OFFER = "offer", "Offer"
    HIRED = "hired", "Hired"
    REJECTED = "rejected", "Not selected"
    WITHDRAWN = "withdrawn", "Withdrawn"


class RejectionReason(models.TextChoices):
    SKILLS_GAP = "skills_gap", "Required skills not shown"
    EXPERIENCE_GAP = "experience_gap", "Experience below what the role needs"
    STRONGER_FIT = "stronger_fit", "Other candidates were a closer fit"
    ROLE_FILLED = "role_filled", "Role filled or closed"
    INTERVIEW_OUTCOME = "interview_outcome", "Interview outcome"
    NO_RESPONSE = "no_response", "Candidate did not respond"
    OTHER = "other", "Other"


class Source(models.TextChoices):
    """Where an application came from (week 4A analytics)."""

    CAREER_SITE = "career_site", "Career site"
    INTERNAL = "internal", "Internal"
    REFERRAL = "referral", "Referral"
    JOB_BOARD = "job_board", "Job board"


class Application(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey("jobs.Job", on_delete=models.PROTECT, related_name="applications")
    candidate = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="applications"
    )
    status = models.CharField(
        max_length=20,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.APPLIED,
        db_index=True,
    )
    cover_note = models.TextField(blank=True, default="")
    source = models.CharField(
        max_length=12, choices=Source.choices, default=Source.CAREER_SITE, db_index=True
    )
    resume_file = models.ForeignKey(
        "files.StoredFile", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    resume_filename = models.CharField(max_length=120, blank=True, default="")
    resume_text = EncryptedTextField(blank=True, default="")
    # Blind screening: set when identity is revealed (automatically at the job's
    # reveal stage, or early by HR with a reason).
    identity_revealed_at = models.DateTimeField(null=True, blank=True)
    revealed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reveal_reason = models.CharField(max_length=300, blank=True, default="")
    # Internal only, never shown to the candidate.
    rejection_reason = models.CharField(
        max_length=20, choices=RejectionReason.choices, blank=True, default=""
    )
    rejection_note = EncryptedTextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["job", "candidate"], name="uniq_application_job_candidate")
        ]

    def __str__(self) -> str:
        return f"{self.candidate_id} -> {self.job_id}"

    @property
    def candidate_code(self) -> str:
        """Stable pseudonym shown while blind, e.g. "Candidate #7F3A"."""
        return f"Candidate #{self.id.hex[:4].upper()}"


class ApplicationEvent(models.Model):
    """Status history, shown to the candidate and to staff."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="events")
    from_status = models.CharField(max_length=20, blank=True, default="")
    to_status = models.CharField(max_length=20)
    reason = models.CharField(max_length=20, blank=True, default="")
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class NoteKind(models.TextChoices):
    NOTE = "note", "Note"
    VOTE = "vote", "Vote"
    CANDIDATE_MESSAGE = "candidate_message", "Message from candidate"


class ApplicationNote(models.Model):
    """Staff notes, hiring-manager thumbs up/down, and messages candidates send via Ask HIRA.

    Never returned to candidates.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    kind = models.CharField(max_length=20, choices=NoteKind.choices, default=NoteKind.NOTE)
    vote = models.CharField(max_length=4, blank=True, default="")  # "up" | "down" | ""
    stage = models.CharField(max_length=20, blank=True, default="")
    body = EncryptedTextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class ApplicationForm(models.Model):
    """The answers to the application form (D-83): personal, education, experience,
    compensation, links, screening answers and the declarations. Stored encrypted. The fit
    scorer never reads it; recruiters see compensation separately from the score."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField(Application, on_delete=models.CASCADE, related_name="form")
    data = EncryptedTextField(blank=True, default="")
    declared_at = models.DateTimeField()
    terms_version = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)


class ApplicationDraft(models.Model):
    """A half-finished application form, saved by the candidate (encrypted)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="application_drafts"
    )
    job = models.ForeignKey("jobs.Job", on_delete=models.CASCADE, related_name="drafts")
    data = EncryptedTextField(blank=True, default="")
    step = models.PositiveSmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["candidate", "job"], name="uniq_draft_per_job")]
        ordering = ["-updated_at"]

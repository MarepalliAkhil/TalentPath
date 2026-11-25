import uuid

from django.conf import settings
from django.db import models


class WorkMode(models.TextChoices):
    ONSITE = "onsite", "On-site"
    HYBRID = "hybrid", "Hybrid"
    REMOTE = "remote", "Remote"


class EmploymentType(models.TextChoices):
    FULL_TIME = "full_time", "Full-time"
    PART_TIME = "part_time", "Part-time"
    CONTRACT = "contract", "Contract"
    INTERNSHIP = "internship", "Internship"


class JobStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    OPEN = "open", "Open"
    CLOSED = "closed", "Closed"


class RevealStage(models.TextChoices):
    INTERVIEW = "interview", "Interview"
    OFFER = "offer", "Offer"


class Audience(models.TextChoices):
    """Week 4A: who may see and apply. Internal jobs are for employees only."""

    BOTH = "both", "Internal and external"
    EXTERNAL = "external", "External (career site)"
    INTERNAL = "internal", "Internal only"


class JobQuerySet(models.QuerySet):
    def open(self):
        return self.filter(status=JobStatus.OPEN)

    def public(self):
        """Open jobs on the public career site (not internal-only)."""
        return self.open().exclude(audience=Audience.INTERNAL)

    def internal(self):
        """Open jobs employees may apply to."""
        return self.open().exclude(audience=Audience.EXTERNAL)


class Job(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=140, unique=True)
    title = models.CharField(max_length=120)
    department = models.ForeignKey("org.Department", on_delete=models.PROTECT, related_name="jobs")
    location = models.ForeignKey("org.Location", on_delete=models.PROTECT, related_name="jobs")
    level = models.ForeignKey("org.JobLevel", on_delete=models.PROTECT, related_name="jobs")
    work_mode = models.CharField(max_length=10, choices=WorkMode.choices, default=WorkMode.HYBRID)
    employment_type = models.CharField(
        max_length=12, choices=EmploymentType.choices, default=EmploymentType.FULL_TIME
    )
    description = models.TextField()
    required_skills = models.ManyToManyField("org.Skill", related_name="jobs_required", blank=True)
    nice_to_have_skills = models.ManyToManyField("org.Skill", related_name="jobs_nice", blank=True)
    openings = models.PositiveSmallIntegerField(default=1)
    # Blind screening: hide identity from staff until the reveal stage.
    blind_screening = models.BooleanField(default=True)
    reveal_stage = models.CharField(max_length=10, choices=RevealStage.choices, default=RevealStage.INTERVIEW)
    audience = models.CharField(max_length=10, choices=Audience.choices, default=Audience.BOTH)
    status = models.CharField(
        max_length=10, choices=JobStatus.choices, default=JobStatus.DRAFT, db_index=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="jobs_created"
    )
    hiring_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="jobs_managed",
    )
    # Prompt 1 (D-84, D-85): the hiring company and the long job page. None of these fields
    # reach the fit scorer; it still reads only the description and the skills.
    company = models.ForeignKey(
        "org.Company", null=True, blank=True, on_delete=models.PROTECT, related_name="jobs"
    )
    about_team = models.TextField(blank=True, default="")
    responsibilities = models.JSONField(default=list, blank=True)
    required_qualifications = models.JSONField(default=list, blank=True)
    preferred_qualifications = models.JSONField(default=list, blank=True)
    benefits = models.JSONField(default=list, blank=True)
    # Compensation range in lakhs per annum (INR), shown on the job page.
    ctc_min_lpa = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    ctc_max_lpa = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    # [{"id": "q1", "text": "...", "kind": "yes_no" | "number" | "text", "required": true}]
    screening_questions = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    objects = JobQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title

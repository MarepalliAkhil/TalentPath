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


class JobQuerySet(models.QuerySet):
    def open(self):
        return self.filter(status=JobStatus.OPEN)


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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    objects = JobQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title

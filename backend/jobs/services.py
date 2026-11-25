from django.db.models import Count
from django.utils import timezone
from django.utils.text import slugify
from rest_framework.exceptions import ValidationError

from accounts.models import Role

from .models import Job, JobStatus

TRANSITIONS = {
    JobStatus.DRAFT: {JobStatus.OPEN},
    JobStatus.OPEN: {JobStatus.CLOSED},
    JobStatus.CLOSED: {JobStatus.OPEN},
}


def unique_job_slug(title: str, location_name: str) -> str:
    base = slugify(f"{title} {location_name}")[:120].strip("-") or "job"
    slug, n = base, 2
    while Job.objects.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


def visible_jobs(user, with_counts: bool = True):
    """Staff scoping: recruiters see jobs they created, hiring managers the
    published jobs they are assigned to, HR sees everything."""
    qs = Job.objects.select_related(
        "department", "location", "level", "created_by", "hiring_manager", "company"
    )
    if with_counts:
        qs = qs.annotate(application_count=Count("applications", distinct=True))
    if user.role == Role.HR:
        return qs
    if user.role == Role.RECRUITER:
        return qs.filter(created_by=user)
    if user.role == Role.MANAGER:
        return qs.filter(hiring_manager=user).exclude(status=JobStatus.DRAFT)
    return qs.none()


def editable_jobs(user):
    if user.role == Role.HR:
        return Job.objects.all()
    if user.role == Role.RECRUITER:
        return Job.objects.filter(created_by=user)
    return Job.objects.none()


def change_status(job: Job, new_status: str) -> Job:
    if new_status not in TRANSITIONS.get(job.status, set()):
        raise ValidationError(
            {"status": f"A {job.get_status_display().lower()} job cannot become {new_status}."}
        )
    if new_status == JobStatus.OPEN:
        problems = []
        if job.hiring_manager_id is None:
            problems.append("Assign a hiring manager.")
        if not job.required_skills.exists():
            problems.append("Add at least one required skill.")
        if problems:
            raise ValidationError({"status": problems})
    now = timezone.now()
    job.status = new_status
    if new_status == JobStatus.OPEN:
        job.published_at = job.published_at or now
        job.closed_at = None
    else:
        job.closed_at = now
    job.save(update_fields=["status", "published_at", "closed_at", "updated_at"])
    return job

from django.db import IntegrityError, transaction
from rest_framework.exceptions import APIException, ValidationError

from accounts.models import Role
from files.storage import save_file
from jobs.models import JobStatus
from notifications.services import notify

from .models import Application, ApplicationEvent
from .models import ApplicationStatus as S
from .resume import CONTENT_TYPES, ResumeError, inspect_resume, safe_filename

# Staff moves in week 1. "hired" is reserved for week 3 (offer -> one-click hire).
STAFF_TRANSITIONS = {
    S.APPLIED: {S.SCREENING, S.REJECTED},
    S.SCREENING: {S.INTERVIEW, S.REJECTED},
    S.INTERVIEW: {S.OFFER, S.REJECTED},
    S.OFFER: {S.REJECTED},
}
WITHDRAWABLE = {S.APPLIED, S.SCREENING, S.INTERVIEW, S.OFFER}


class DuplicateApplication(APIException):
    status_code = 409
    default_detail = "You have already applied to this job."
    default_code = "duplicate_application"


def apply_to_job(*, candidate, job, filename: str, data: bytes, cover_note: str = "", silent=False):
    if job.status != JobStatus.OPEN:
        raise ValidationError({"job": "This job is not accepting applications."})
    if Application.objects.filter(job=job, candidate=candidate).exists():
        raise DuplicateApplication()
    try:
        kind, text = inspect_resume(data)
    except ResumeError as exc:
        raise ValidationError({"resume": str(exc)}) from exc
    name = safe_filename(filename, kind)
    with transaction.atomic():
        stored = save_file(owner=candidate, original_name=name, content_type=CONTENT_TYPES[kind], raw=data)
        try:
            with transaction.atomic():
                application = Application.objects.create(
                    job=job,
                    candidate=candidate,
                    cover_note=cover_note.strip()[:2000],
                    resume_file=stored,
                    resume_filename=name,
                    resume_text=text,
                )
        except IntegrityError as exc:
            raise DuplicateApplication() from exc
        ApplicationEvent.objects.create(
            application=application, from_status="", to_status=S.APPLIED, actor=candidate
        )
    if not silent:
        notify(
            candidate,
            kind="application_received",
            title=f"Application received: {job.title}",
            body=f"Thanks for applying to {job.title}. We will update you here as it moves forward.",
            link="/candidate",
        )
        notify(
            job.created_by,
            kind="new_application",
            title=f"New application for {job.title}",
            body=f"{candidate.full_name} applied to {job.title}.",
            link=f"/recruiter/jobs/{job.id}/applications",
        )
    return application


def _record(application, old, new, actor):
    application.status = new
    application.save(update_fields=["status", "updated_at"])
    ApplicationEvent.objects.create(application=application, from_status=old, to_status=new, actor=actor)


def move_application(application, new_status: str, actor, silent=False):
    old = application.status
    if new_status not in STAFF_TRANSITIONS.get(old, set()):
        raise ValidationError({"status": f"Cannot move an application from {old} to {new_status}."})
    _record(application, old, new_status, actor)
    if not silent:
        label = S(new_status).label
        body = (
            f"Thank you for your interest in {application.job.title}. We will not be moving "
            "forward this time, and we encourage you to apply for other roles."
            if new_status == S.REJECTED
            else f"Your application for {application.job.title} is now at: {label}."
        )
        notify(
            application.candidate,
            kind="application_status",
            title=f"Update on {application.job.title}: {label}",
            body=body,
            link="/candidate",
        )
    return application


def withdraw_application(application, actor):
    if application.status not in WITHDRAWABLE:
        raise ValidationError({"status": "This application can no longer be withdrawn."})
    _record(application, application.status, S.WITHDRAWN, actor)
    return application


def staff_visible_applications(user):
    qs = Application.objects.select_related("job", "candidate", "candidate__profile")
    if user.role == Role.HR_ADMIN:
        return qs
    if user.role == Role.RECRUITER:
        return qs.filter(job__created_by=user)
    if user.role == Role.HIRING_MANAGER:
        return qs.filter(job__hiring_manager=user).exclude(job__status=JobStatus.DRAFT)
    return qs.none()


def visible_applications(user):
    if user.role == Role.CANDIDATE:
        return Application.objects.select_related("job", "job__department", "job__location").filter(
            candidate=user
        )
    return staff_visible_applications(user)

from django.db import IntegrityError, transaction
from rest_framework.exceptions import APIException, ValidationError

from accounts.models import Role, User
from core.audit import audit
from files.storage import save_file
from jobs.models import Job, JobStatus
from notifications.services import notify, push_realtime

from .blind import is_blind, maybe_auto_reveal
from .models import Application, ApplicationEvent, ApplicationNote, NoteKind, RejectionReason
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
BULK_TARGETS = {S.SCREENING, S.REJECTED}
HM_NOTE_STAGES = {S.SCREENING, S.INTERVIEW}

# Customer-safe stage words for candidates.
CANDIDATE_STATUS_WORDS = {
    S.APPLIED: "Received",
    S.SCREENING: "Under review",
    S.INTERVIEW: "Interview stage",
    S.OFFER: "Offer stage",
    S.HIRED: "Hired",
    S.REJECTED: "Not progressing",
    S.WITHDRAWN: "Withdrawn",
}


class DuplicateApplication(APIException):
    status_code = 409
    default_detail = "You have already applied to this job."
    default_code = "duplicate_application"


def apply_to_job(
    *,
    candidate,
    job,
    filename: str,
    data: bytes,
    cover_note: str = "",
    silent=False,
    source: str = "career_site",
):
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
                    source=source,
                    resume_file=stored,
                    resume_filename=name,
                    resume_text=text,
                )
        except IntegrityError as exc:
            raise DuplicateApplication() from exc
        ApplicationEvent.objects.create(
            application=application, from_status="", to_status=S.APPLIED, actor=candidate
        )
    from matching.services import process_application

    process_application(application)
    broadcast_board(application, event="new")
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
            body=(
                f"{application.candidate_code} applied to {job.title}."
                if is_blind(application)
                else f"{candidate.full_name} applied to {job.title}."
            ),
            link=f"/recruiter/jobs/{job.id}/applications",
        )
    return application


def _record(application, old, new, actor, reason=""):
    application.status = new
    application.save(update_fields=["status", "updated_at"])
    ApplicationEvent.objects.create(
        application=application, from_status=old, to_status=new, actor=actor, reason=reason
    )


def _coordinate(application, old, new, actor, silent) -> None:
    """Hand stage changes to HIRA (interview scheduling, cancelling interviews)."""
    from interviews.coordinator import on_stage_changed

    on_stage_changed(application, old, new, actor=actor, silent=silent)


def board_viewers(job) -> set:
    """Everyone who can see this job's board and should get live updates."""
    ids = {job.created_by_id}
    if job.hiring_manager_id:
        ids.add(job.hiring_manager_id)
    ids.update(User.objects.filter(role=Role.HR_ADMIN, is_active=True).values_list("id", flat=True))
    return ids


def broadcast_board(application, event: str = "moved") -> None:
    payload = {
        "type": "board",
        "event": event,
        "job": str(application.job_id),
        "application": str(application.id),
        "status": application.status,
    }
    for user_id in board_viewers(application.job):
        push_realtime(user_id, payload)


def suggested_jobs(application, limit: int = 3) -> list:
    """Open jobs that match skills on the candidate's resume (for kind rejection messages)."""
    from matching.services import profile_skill_slugs

    skills = profile_skill_slugs(application.candidate)
    if not skills:
        return []
    applied = Application.objects.filter(candidate=application.candidate).values("job_id")
    scored = []
    for job in Job.objects.public().exclude(pk__in=applied).prefetch_related("required_skills"):
        overlap = len(skills & {s.slug for s in job.required_skills.all()})
        if overlap:
            scored.append((overlap, job.title, job))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [job for _, _, job in scored[:limit]]


def rejection_message(application) -> str:
    """Kind and short. Never mentions the score, the reason or anything personal."""
    title = application.job.title
    lines = [
        f"Thank you for applying to {title} and for the time you put into it.",
        "We have decided not to move forward with your application for this role.",
    ]
    jobs = suggested_jobs(application)
    if jobs:
        lines.append(
            "These open roles match skills on your resume: " + "; ".join(j.title for j in jobs) + "."
        )
    lines.append("We would be glad to see you apply again.")
    return " ".join(lines)


def move_application(
    application, new_status: str, actor, *, silent=False, reason: str = "", note: str = "", request=None
):
    old = application.status
    if new_status not in STAFF_TRANSITIONS.get(old, set()):
        raise ValidationError({"status": f"Cannot move an application from {old} to {new_status}."})
    if new_status == S.REJECTED:
        if reason not in RejectionReason.values:
            raise ValidationError({"reason": "Choose a reason for not moving forward."})
        application.rejection_reason = reason
        application.rejection_note = (note or "").strip()[:2000]
        application.save(update_fields=["rejection_reason", "rejection_note", "updated_at"])
    _record(application, old, new_status, actor, reason=reason if new_status == S.REJECTED else "")
    maybe_auto_reveal(application, actor=actor, request=request)
    audit(request, "applications.status", actor=actor, target=application, old=old, new=new_status)
    broadcast_board(application)
    _coordinate(application, old, new_status, actor, silent)
    from growth.services import internal_stage_notice

    internal_stage_notice(application, new_status)
    if not silent:
        label = CANDIDATE_STATUS_WORDS.get(new_status, S(new_status).label)
        body = (
            rejection_message(application)
            if new_status == S.REJECTED
            else f"Your application for {application.job.title} has moved to: {label}."
        )
        notify(
            application.candidate,
            kind="application_status",
            title=f"Update on {application.job.title}: {label}",
            body=body,
            link="/internal-jobs"
            if application.source == "internal"
            else "/jobs"
            if new_status == S.REJECTED
            else "/candidate",
        )
    return application


@transaction.atomic
def bulk_move(applications, new_status: str, actor, *, reason: str = "", note: str = "", request=None):
    """All or nothing: every application must allow the move."""
    if new_status not in BULK_TARGETS:
        raise ValidationError({"status": "Bulk moves can go to Screening or Not selected only."})
    problems = [
        app.candidate_code
        for app in applications
        if new_status not in STAFF_TRANSITIONS.get(app.status, set())
    ]
    if problems:
        raise ValidationError({"status": f"Cannot move {', '.join(problems)} to {new_status}."})
    for app in applications:
        move_application(app, new_status, actor, reason=reason, note=note, request=request)
    return applications


def add_note(application, author, *, body: str = "", vote: str = "", request=None) -> ApplicationNote:
    body = (body or "").strip()
    vote = (vote or "").strip()
    if vote not in ("", "up", "down"):
        raise ValidationError({"vote": "Use up or down."})
    if not body and not vote:
        raise ValidationError({"body": "Write a note or choose thumbs up or down."})
    if len(body) > 2000:
        raise ValidationError({"body": "Keep notes under 2000 characters."})
    if author.role == Role.HIRING_MANAGER and application.status not in HM_NOTE_STAGES:
        raise ValidationError({"status": "Hiring managers add notes at the Screening and Interview stages."})
    if vote and author.role != Role.HIRING_MANAGER:
        raise ValidationError({"vote": "Thumbs up or down is for the hiring manager."})
    note = ApplicationNote.objects.create(
        application=application,
        author=author,
        kind=NoteKind.VOTE if vote else NoteKind.NOTE,
        vote=vote,
        stage=application.status,
        body=body,
    )
    audit(request, "applications.note", actor=author, target=application, vote=vote or None)
    broadcast_board(application, event="note")
    return note


def add_candidate_message(application, candidate, body: str, request=None) -> ApplicationNote:
    body = (body or "").strip()
    if not body:
        raise ValidationError({"message": "Write a message for the recruiter."})
    if len(body) > 1000:
        raise ValidationError({"message": "Keep the message under 1000 characters."})
    note = ApplicationNote.objects.create(
        application=application,
        author=candidate,
        kind=NoteKind.CANDIDATE_MESSAGE,
        stage=application.status,
        body=body,
    )
    who = application.candidate_code if is_blind(application) else candidate.full_name
    notify(
        application.job.created_by,
        kind="candidate_message",
        title=f"Message from {who} about {application.job.title}",
        body="A candidate sent a message through Ask HIRA. Open the application to read it.",
        link=f"/recruiter/jobs/{application.job_id}/applications",
    )
    audit(request, "applications.candidate_message", actor=candidate, target=application)
    return note


def withdraw_application(application, actor):
    """Only the candidate can withdraw (enforced by policy and by the view's queryset)."""
    if application.status not in WITHDRAWABLE:
        raise ValidationError({"status": "This application can no longer be withdrawn."})
    old = application.status
    _record(application, old, S.WITHDRAWN, actor)
    broadcast_board(application)
    _coordinate(application, old, S.WITHDRAWN, actor, silent=True)
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

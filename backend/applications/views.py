import json

from django.conf import settings
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from accounts.models import Role, User
from core.audit import audit
from core.demo import check_demo_upload, deny_demo
from core.utils import IgnoreClientContentNegotiation, paginate
from core.views import PolicyAPIView
from files.storage import read_file
from jobs.models import Job, JobStatus
from jobs.services import visible_jobs
from matching.services import ensure_fresh, fit_dict
from org.taxonomy import resolve_skill

from .blind import is_blind, redacted_text, reveal
from .models import Application, ApplicationNote, NoteKind, RejectionReason
from .models import ApplicationStatus as S
from .services import (
    CANDIDATE_STATUS_WORDS,
    STAFF_TRANSITIONS,
    add_note,
    apply_to_job,
    bulk_move,
    move_application,
    visible_applications,
    withdraw_application,
)

BOARD_COLUMNS = [S.APPLIED, S.SCREENING, S.INTERVIEW, S.OFFER, S.HIRED, S.REJECTED, S.WITHDRAWN]
RESERVED_COLUMNS = {
    S.HIRED: "One-click hire arrives in week 3",
    S.WITHDRAWN: "Only the candidate can withdraw",
}


class PostOnlyScopedThrottle(ScopedRateThrottle):
    def allow_request(self, request, view):
        if request.method != "POST":
            return True
        return super().allow_request(request, view)


def _events(app, staff: bool = False):
    out = []
    for e in app.events.all():
        row = {
            "to_status": e.to_status,
            "label": S(e.to_status).label if staff else CANDIDATE_STATUS_WORDS.get(e.to_status, e.to_status),
            "at": e.created_at.isoformat(),
        }
        if staff and e.reason:
            row["reason"] = (
                RejectionReason(e.reason).label if e.reason in RejectionReason.values else e.reason
            )
        out.append(row)
    return out


def candidate_application_dict(app: Application, detail: bool = False) -> dict:
    """What a candidate sees about their own application: no score, notes or reasons."""
    job = app.job
    data = {
        "id": str(app.id),
        "status": app.status,
        "status_label": CANDIDATE_STATUS_WORDS.get(app.status, app.get_status_display()),
        "created_at": app.created_at.isoformat(),
        "updated_at": app.updated_at.isoformat(),
        "resume_filename": app.resume_filename,
        "can_withdraw": app.status in {S.APPLIED, S.SCREENING, S.INTERVIEW, S.OFFER},
        "job": {
            "slug": job.slug,
            "title": job.title,
            "department": job.department.name,
            "location": job.location.name,
            "is_open": job.status == JobStatus.OPEN,
        },
    }
    if detail:
        data["cover_note"] = app.cover_note
        data["events"] = _events(app)
    return data


def _candidate_block(app: Application, blind: bool) -> dict:
    if blind:
        return {
            "id": None,
            "code": app.candidate_code,
            "full_name": None,
            "email": None,
            "headline": None,
            "location": None,
        }
    profile = getattr(app.candidate, "profile", None)
    return {
        "id": str(app.candidate_id),
        "code": app.candidate_code,
        "full_name": app.candidate.full_name,
        "email": app.candidate.email,
        "headline": profile.headline if profile else "",
        "location": profile.location_text if profile else "",
    }


def _skill_list(app: Application) -> list:
    profile = app.parsed_profile if hasattr(app, "parsed_profile") else None
    return [
        {"slug": s["slug"], "name": s["name"], "section": s["section"]}
        for s in (profile.skills if profile else [])
    ]


def staff_application_dict(app: Application, viewer: User, detail: bool = False) -> dict:
    """Staff view. While blind, identity fields are None and resume text is redacted server-side."""
    blind = is_blind(app)
    can_move = viewer.role in (Role.RECRUITER, Role.HR_ADMIN)
    data = {
        "id": str(app.id),
        "status": app.status,
        "status_label": app.get_status_display(),
        "source": app.source,
        "source_label": app.get_source_display(),
        "created_at": app.created_at.isoformat(),
        "updated_at": app.updated_at.isoformat(),
        "resume_filename": None if blind else app.resume_filename,
        "blind": blind,
        "candidate": _candidate_block(app, blind),
        "job": {"id": str(app.job_id), "title": app.job.title, "slug": app.job.slug},
        "allowed_transitions": sorted(str(s) for s in STAFF_TRANSITIONS.get(app.status, set()))
        if can_move
        else [],
        "fit": fit_dict(app),
        "skills": _skill_list(app),
    }
    if app.status == S.REJECTED and app.rejection_reason:
        data["rejection_reason"] = RejectionReason(app.rejection_reason).label
    if detail:
        text = app.resume_text or ""
        data["resume_text"] = redacted_text(app, text) if blind else text
        data["cover_note"] = redacted_text(app, app.cover_note) if blind else app.cover_note
        data["events"] = _events(app, staff=True)
        data["rejection_note"] = app.rejection_note if app.status == S.REJECTED else ""
        data["evidence"] = _evidence(app, blind)
        data["notes"] = [note_dict(n, app) for n in app.notes.select_related("author")]
        data["revealed"] = (
            {"at": app.identity_revealed_at.isoformat(), "reason": app.reveal_reason}
            if app.identity_revealed_at
            else None
        )
        data["reveal_stage"] = app.job.reveal_stage
    return data


def _evidence(app: Application, blind: bool) -> list:
    profile = app.parsed_profile if hasattr(app, "parsed_profile") else None
    if profile is None:
        return []
    try:
        rows = json.loads(profile.evidence or "[]")
    except ValueError:
        rows = []
    names = {s["slug"]: (s["name"], s["section"]) for s in profile.skills}
    out = []
    for row in rows:
        name, section = names.get(row["slug"], (row["slug"], ""))
        snippet = redacted_text(app, row["snippet"]) if blind else row["snippet"]
        out.append({"slug": row["slug"], "name": name, "section": section, "snippet": snippet})
    return out


def note_dict(note: ApplicationNote, app: Application) -> dict:
    author = note.author
    if note.kind == NoteKind.CANDIDATE_MESSAGE:
        who = app.candidate_code if is_blind(app) else (author.full_name if author else "Candidate")
        role = "candidate"
    else:
        who = author.full_name if author else "Former staff"
        role = author.role if author else ""
    return {
        "id": str(note.id),
        "kind": note.kind,
        "vote": note.vote or None,
        "stage": note.stage,
        "body": note.body,
        "author": who,
        "author_role": role,
        "created_at": note.created_at.isoformat(),
    }


class ApplicationListCreateView(PolicyAPIView):
    policy_actions = {"GET": "applications.list_mine", "POST": "applications.create"}
    throttle_classes = [PostOnlyScopedThrottle]
    throttle_scope = "upload"

    def get(self, request):
        qs = visible_applications(request.user).order_by("-created_at")
        return paginate(self, request, qs, candidate_application_dict)

    def post(self, request):
        length = int(request.META.get("CONTENT_LENGTH") or 0)
        if length > settings.RESUME_MAX_BYTES + 256 * 1024:
            return Response(
                {"resume": ["Resumes must be 5 MB or smaller."]},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        slug = str(request.data.get("job", "")).strip()
        upload = request.FILES.get("resume")
        errors = {}
        if not slug:
            errors["job"] = ["Choose a job."]
        if upload is None:
            errors["resume"] = ["Attach your resume (PDF or DOCX)."]
        elif upload.size > settings.RESUME_MAX_BYTES:
            errors["resume"] = ["Resumes must be 5 MB or smaller."]
        cover_note = str(request.data.get("cover_note", ""))
        if len(cover_note) > 2000:
            errors["cover_note"] = ["Keep the note under 2000 characters."]
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        job = get_object_or_404(Job.objects.public(), slug=slug)
        source = str(request.data.get("source") or "career_site")
        if source not in ("career_site", "referral", "job_board"):
            return Response({"source": ["Choose career site, referral or job board."]}, status=400)
        data = upload.read(settings.RESUME_MAX_BYTES + 1)
        check_demo_upload(request.user, len(data))
        application = apply_to_job(
            candidate=request.user,
            job=job,
            filename=upload.name,
            data=data,
            cover_note=cover_note,
            source=source,
        )
        audit(request, "applications.create", target=application, job=str(job.id))
        return Response(candidate_application_dict(application, detail=True), status=201)


def _staff_app(request, pk):
    qs = visible_applications(request.user).select_related("job__level", "parsed_profile", "fit_score")
    return get_object_or_404(qs, pk=pk)


class ApplicationDetailView(PolicyAPIView):
    policy_action = "applications.read"

    def get(self, request, pk):
        if request.user.role == Role.CANDIDATE:
            app = get_object_or_404(visible_applications(request.user), pk=pk)
            return Response(candidate_application_dict(app, detail=True))
        app = _staff_app(request, pk)
        ensure_fresh([app])
        audit(request, "applications.view", target=app, blind=is_blind(app))
        return Response(staff_application_dict(app, request.user, detail=True))


class ApplicationWithdrawView(PolicyAPIView):
    policy_action = "applications.withdraw"

    def post(self, request, pk):
        app = get_object_or_404(Application.objects.filter(candidate=request.user), pk=pk)
        withdraw_application(app, request.user)
        audit(request, "applications.withdraw", target=app)
        return Response(candidate_application_dict(app, detail=True))


class ApplicationStatusView(PolicyAPIView):
    policy_action = "applications.status"

    def post(self, request, pk):
        app = _staff_app(request, pk)
        move_application(
            app,
            str(request.data.get("status", "")),
            request.user,
            reason=str(request.data.get("reason", "") or ""),
            note=str(request.data.get("note", "") or ""),
            request=request,
        )
        return Response(staff_application_dict(app, request.user))


class BulkStatusView(PolicyAPIView):
    policy_action = "applications.bulk_status"

    def post(self, request, pk):
        deny_demo(request.user, "move applications in bulk")
        job = get_object_or_404(visible_jobs(request.user, with_counts=False), pk=pk)
        ids = request.data.get("ids") or []
        if not isinstance(ids, list) or not ids or len(ids) > 100:
            return Response({"ids": "Choose between 1 and 100 applications."}, status=400)
        apps = list(Application.objects.filter(job=job, pk__in=[str(i) for i in ids]).select_related("job"))
        if len(apps) != len(set(map(str, ids))):
            return Response({"ids": "Some applications are not part of this job."}, status=400)
        bulk_move(
            apps,
            str(request.data.get("status", "")),
            request.user,
            reason=str(request.data.get("reason", "") or ""),
            note=str(request.data.get("note", "") or ""),
            request=request,
        )
        return Response({"moved": len(apps), "status": apps[0].status})


class RevealView(PolicyAPIView):
    """Early identity reveal: hr_admin only (policy), always with a reason, always audited."""

    policy_action = "applications.reveal"

    def post(self, request, pk):
        app = _staff_app(request, pk)
        reason = str(request.data.get("reason", "")).strip()
        if len(reason) < 10:
            return Response({"reason": "Give a reason of at least 10 characters."}, status=400)
        if not is_blind(app):
            return Response({"detail": "This candidate's identity is already visible."}, status=409)
        reveal(app, actor=request.user, reason=reason, request=request, automatic=False)
        return Response(staff_application_dict(app, request.user, detail=True))


class NotesView(PolicyAPIView):
    policy_actions = {"GET": "applications.notes", "POST": "applications.notes"}

    def get(self, request, pk):
        app = _staff_app(request, pk)
        return Response([note_dict(n, app) for n in app.notes.select_related("author")])

    def post(self, request, pk):
        app = _staff_app(request, pk)
        note = add_note(
            app,
            request.user,
            body=str(request.data.get("body", "") or ""),
            vote=str(request.data.get("vote", "") or ""),
            request=request,
        )
        return Response(note_dict(note, app), status=201)


class ResumeDownloadView(PolicyAPIView):
    policy_action = "applications.resume"
    content_negotiation_class = IgnoreClientContentNegotiation

    def get(self, request, pk):
        app = get_object_or_404(visible_applications(request.user), pk=pk)
        if request.user.role != Role.CANDIDATE and is_blind(app):
            # The original file carries the candidate's identity: never sent while blind.
            return Response(
                {"detail": "The original file is hidden during blind screening.", "code": "identity_hidden"},
                status=status.HTTP_409_CONFLICT,
            )
        if app.resume_file is None:
            return Response({"detail": "No resume stored."}, status=404)
        stored = app.resume_file
        audit(request, "applications.resume_download", target=app)
        response = HttpResponse(read_file(stored), content_type=stored.content_type)
        response["Content-Disposition"] = f'attachment; filename="{app.resume_filename}"'
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response


def _job_apps(job):
    return list(
        Application.objects.filter(job=job)
        .select_related("job__level", "candidate__profile", "parsed_profile", "fit_score")
        .order_by("-created_at")
    )


def _sort_key(app):
    fit = app.fit_score if hasattr(app, "fit_score") else None
    return (-(fit.score if fit else -1), app.created_at)


class JobApplicationsView(PolicyAPIView):
    """Ranked list: candidates ordered by fit score, filterable by band, skill and stage."""

    policy_action = "jobs.applications"

    def get(self, request, pk):
        job = get_object_or_404(visible_jobs(request.user), pk=pk)
        apps = _job_apps(job)
        ensure_fresh(apps)
        p = request.query_params
        if p.get("status"):
            apps = [a for a in apps if a.status == p["status"]]
        if p.get("band"):
            bands = set(p["band"].split(","))
            apps = [a for a in apps if hasattr(a, "fit_score") and a.fit_score.band in bands]
        if p.get("skill"):
            skill = resolve_skill(p["skill"])
            slug = skill.slug if skill else None
            apps = [a for a in apps if slug and slug in {s["slug"] for s in _skill_list(a)}]
        apps.sort(key=_sort_key)
        response = paginate(self, request, apps, lambda a: staff_application_dict(a, request.user))
        response.data["job"] = {
            "id": str(job.id),
            "title": job.title,
            "status": job.status,
            "blind_screening": job.blind_screening,
            "reveal_stage": job.reveal_stage,
        }
        return response


class JobBoardView(PolicyAPIView):
    policy_action = "jobs.board"

    def get(self, request, pk):
        job = get_object_or_404(visible_jobs(request.user), pk=pk)
        apps = _job_apps(job)
        ensure_fresh(apps)
        apps.sort(key=_sort_key)
        columns = []
        for stage in BOARD_COLUMNS:
            cards = [staff_application_dict(a, request.user) for a in apps if a.status == stage]
            columns.append(
                {
                    "status": stage,
                    "label": S(stage).label,
                    "drop_target": stage not in RESERVED_COLUMNS,
                    "note": RESERVED_COLUMNS.get(stage, ""),
                    "cards": cards,
                }
            )
        return Response(
            {
                "job": {
                    "id": str(job.id),
                    "title": job.title,
                    "status": job.status,
                    "blind_screening": job.blind_screening,
                    "reveal_stage": job.reveal_stage,
                },
                "can_move": request.user.role in (Role.RECRUITER, Role.HR_ADMIN),
                "can_note": request.user.role in (Role.RECRUITER, Role.HIRING_MANAGER, Role.HR_ADMIN),
                "transitions": {str(k): sorted(str(v) for v in vs) for k, vs in STAFF_TRANSITIONS.items()},
                "rejection_reasons": [{"value": v, "label": label} for v, label in RejectionReason.choices],
                "columns": columns,
            }
        )


def _counts(qs, field):
    return {row[field]: row["n"] for row in qs.values(field).annotate(n=Count("pk"))}


class DashboardSummaryView(PolicyAPIView):
    policy_action = "dashboard.summary"

    def get(self, request):
        user = request.user
        data = {"role": user.role}
        if user.role == Role.CANDIDATE:
            mine = Application.objects.filter(candidate=user)
            data["applications_by_status"] = _counts(mine, "status")
            data["applications_total"] = mine.count()
            data["open_jobs"] = Job.objects.open().count()
        elif user.role in (Role.RECRUITER, Role.HIRING_MANAGER, Role.HR_ADMIN):
            jobs = visible_jobs(user, with_counts=False)
            data["jobs_by_status"] = _counts(jobs, "status")
            apps = Application.objects.filter(job__in=jobs.values("pk"))
            data["applications_by_status"] = _counts(apps, "status")
            data["applications_total"] = apps.count()
            if user.role == Role.HR_ADMIN:
                data["users_by_role"] = _counts(User.objects.filter(is_active=True), "role")
        return Response(data)

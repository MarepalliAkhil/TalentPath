from django.conf import settings
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from accounts.models import Role, User
from core.audit import audit
from core.utils import IgnoreClientContentNegotiation, paginate
from core.views import PolicyAPIView
from files.storage import read_file
from jobs.models import Job, JobStatus
from jobs.services import visible_jobs

from .models import Application
from .models import ApplicationStatus as S
from .services import (
    STAFF_TRANSITIONS,
    apply_to_job,
    move_application,
    visible_applications,
    withdraw_application,
)


class PostOnlyScopedThrottle(ScopedRateThrottle):
    def allow_request(self, request, view):
        if request.method != "POST":
            return True
        return super().allow_request(request, view)


def _events(app):
    return [
        {"to_status": e.to_status, "label": S(e.to_status).label, "at": e.created_at.isoformat()}
        for e in app.events.all()
    ]


def candidate_application_dict(app: Application, detail: bool = False) -> dict:
    job = app.job
    data = {
        "id": str(app.id),
        "status": app.status,
        "status_label": app.get_status_display(),
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


def staff_application_dict(app: Application, detail: bool = False) -> dict:
    profile = getattr(app.candidate, "profile", None)
    data = {
        "id": str(app.id),
        "status": app.status,
        "status_label": app.get_status_display(),
        "created_at": app.created_at.isoformat(),
        "resume_filename": app.resume_filename,
        "candidate": {
            "id": str(app.candidate_id),
            "full_name": app.candidate.full_name,
            "email": app.candidate.email,
            "headline": profile.headline if profile else "",
            "location": profile.location_text if profile else "",
        },
        "job": {"id": str(app.job_id), "title": app.job.title, "slug": app.job.slug},
        "allowed_transitions": sorted(str(s) for s in STAFF_TRANSITIONS.get(app.status, set())),
    }
    if detail:
        data["cover_note"] = app.cover_note
        data["resume_text"] = app.resume_text
        data["events"] = _events(app)
    return data


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
        job = get_object_or_404(Job, slug=slug, status=JobStatus.OPEN)
        data = upload.read(settings.RESUME_MAX_BYTES + 1)
        application = apply_to_job(
            candidate=request.user,
            job=job,
            filename=upload.name,
            data=data,
            cover_note=cover_note,
        )
        audit(request, "applications.create", target=application, job=str(job.id))
        return Response(candidate_application_dict(application, detail=True), status=201)


class ApplicationDetailView(PolicyAPIView):
    policy_action = "applications.read"

    def get(self, request, pk):
        app = get_object_or_404(visible_applications(request.user), pk=pk)
        if request.user.role == Role.CANDIDATE:
            return Response(candidate_application_dict(app, detail=True))
        audit(request, "applications.view", target=app)
        return Response(staff_application_dict(app, detail=True))


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
        app = get_object_or_404(visible_applications(request.user), pk=pk)
        old = app.status
        move_application(app, str(request.data.get("status", "")), request.user)
        audit(request, "applications.status", target=app, old=old, new=app.status)
        return Response(staff_application_dict(app))


class ResumeDownloadView(PolicyAPIView):
    policy_action = "applications.resume"
    content_negotiation_class = IgnoreClientContentNegotiation

    def get(self, request, pk):
        app = get_object_or_404(visible_applications(request.user), pk=pk)
        if app.resume_file is None:
            return Response({"detail": "No resume stored."}, status=404)
        stored = app.resume_file
        audit(request, "applications.resume_download", target=app)
        response = HttpResponse(read_file(stored), content_type=stored.content_type)
        response["Content-Disposition"] = f'attachment; filename="{app.resume_filename}"'
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class JobApplicationsView(PolicyAPIView):
    policy_action = "jobs.applications"

    def get(self, request, pk):
        job = get_object_or_404(visible_jobs(request.user), pk=pk)
        qs = (
            Application.objects.filter(job=job)
            .select_related("job", "candidate", "candidate__profile")
            .order_by("-created_at")
        )
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        response = paginate(self, request, qs, staff_application_dict)
        response.data["job"] = {"id": str(job.id), "title": job.title, "status": job.status}
        return response


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

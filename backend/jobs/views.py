from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from core.audit import audit
from core.demo import deny_demo
from core.utils import paginate
from core.views import PolicyAPIView
from org.taxonomy import resolve_skill

from .models import Job, JobStatus, WorkMode
from .serializers import JobWriteSerializer, public_job_dict, staff_job_dict
from .services import change_status, editable_jobs, unique_job_slug, visible_jobs


def _public_qs():
    return (
        Job.objects.public()
        .select_related("department", "location", "level", "company")
        .prefetch_related("required_skills", "nice_to_have_skills")
        .order_by("-published_at", "-created_at")
    )


class CareerJobListView(PolicyAPIView):
    policy_action = "careers.list"

    def get(self, request):
        qs = _public_qs()
        p = request.query_params
        q = p.get("q", "").strip()[:100]
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
        if p.get("department"):
            qs = qs.filter(department__slug=p["department"])
        if p.get("location"):
            qs = qs.filter(location__slug=p["location"])
        if p.get("company"):
            qs = qs.filter(company__slug=p["company"])
        if p.get("work_mode"):
            if p["work_mode"] not in WorkMode.values:
                return Response({"work_mode": "Unknown work mode."}, status=400)
            qs = qs.filter(work_mode=p["work_mode"])
        if p.get("skill"):
            skill = resolve_skill(p["skill"])
            if skill is None:
                qs = qs.none()
            else:
                qs = qs.filter(Q(required_skills=skill) | Q(nice_to_have_skills=skill)).distinct()
        return paginate(self, request, qs, public_job_dict)


class CareerJobDetailView(PolicyAPIView):
    policy_action = "careers.detail"

    def get(self, request, slug):
        job = get_object_or_404(_public_qs(), slug=slug)
        return Response(public_job_dict(job, detail=True))


# Editing any of these recomputes every fit score for the job.
SCORING_FIELDS = {"required_skills", "nice_to_have_skills", "description", "level"}


class StaffJobListView(PolicyAPIView):
    policy_actions = {"GET": "jobs.list", "POST": "jobs.create"}

    def get(self, request):
        qs = visible_jobs(request.user).prefetch_related("required_skills", "nice_to_have_skills")
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return paginate(self, request, qs.order_by("-created_at"), staff_job_dict)

    def post(self, request):
        serializer = JobWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        v = serializer.validated_data
        job = serializer.save(
            created_by=request.user,
            status=JobStatus.DRAFT,
            slug=unique_job_slug(v["title"], v["location"].name),
        )
        audit(request, "jobs.create", target=job)
        return Response(staff_job_dict(visible_jobs(request.user).get(pk=job.pk)), status=201)


class StaffJobDetailView(PolicyAPIView):
    policy_actions = {"GET": "jobs.read", "PATCH": "jobs.update", "DELETE": "jobs.delete"}

    def get(self, request, pk):
        return Response(staff_job_dict(get_object_or_404(visible_jobs(request.user), pk=pk)))

    def patch(self, request, pk):
        job = get_object_or_404(editable_jobs(request.user), pk=pk)
        if job.status == JobStatus.CLOSED:
            return Response({"detail": "Reopen the job before editing it."}, status=400)
        serializer = JobWriteSerializer(job, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        changed = set(serializer.validated_data)
        if changed & SCORING_FIELDS:
            from matching.services import rescore_job

            rescore_job(job)
        audit(request, "jobs.update", target=job, fields=sorted(changed))
        return Response(staff_job_dict(visible_jobs(request.user).get(pk=job.pk)))

    def delete(self, request, pk):
        deny_demo(request.user, "delete jobs")
        job = get_object_or_404(editable_jobs(request.user), pk=pk)
        if job.status != JobStatus.DRAFT or job.applications.exists():
            return Response(
                {"detail": "Only draft jobs without applications can be deleted. Close it instead."},
                status=status.HTTP_409_CONFLICT,
            )
        audit(request, "jobs.delete", target=job, title=job.title)
        job.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class StaffJobStatusView(PolicyAPIView):
    policy_action = "jobs.status"

    def post(self, request, pk):
        job = get_object_or_404(editable_jobs(request.user), pk=pk)
        old = job.status
        change_status(job, str(request.data.get("status", "")))
        audit(request, "jobs.status", target=job, old=old, new=job.status)
        return Response(staff_job_dict(visible_jobs(request.user).get(pk=job.pk)))

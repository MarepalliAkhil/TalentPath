from django.conf import settings
from rest_framework import status
from rest_framework.response import Response

from applications.views import PostOnlyScopedThrottle
from core.demo import check_demo_upload
from core.views import PolicyAPIView

from . import services


class CareerProfileView(PolicyAPIView):
    """The person's own resume for the career map and internal applications."""

    policy_action = "career.profile"
    throttle_classes = [PostOnlyScopedThrottle]
    throttle_scope = "upload"

    def get(self, request):
        return Response(services.profile_dict(request.user))

    def post(self, request):
        length = int(request.META.get("CONTENT_LENGTH") or 0)
        if length > settings.RESUME_MAX_BYTES + 256 * 1024:
            return Response({"resume": ["Resumes must be 5 MB or smaller."]}, status=413)
        upload = request.FILES.get("resume")
        if upload is None:
            return Response({"resume": ["Attach your resume (PDF or DOCX)."]}, status=400)
        if upload.size > settings.RESUME_MAX_BYTES:
            return Response({"resume": ["Resumes must be 5 MB or smaller."]}, status=400)
        data = upload.read(settings.RESUME_MAX_BYTES + 1)
        check_demo_upload(request.user, len(data))
        services.save_profile_resume(request.user, upload.name, data, request=request)
        return Response(services.profile_dict(request.user), status=status.HTTP_201_CREATED)

    def delete(self, request):
        services.delete_profile_resume(request.user, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CareerMapView(PolicyAPIView):
    """Jobs you're closest to, ranked by the same scorer recruiters see."""

    policy_action = "career.map"

    def get(self, request):
        return Response(services.closest_jobs(request.user))


class CareerJobMapView(PolicyAPIView):
    policy_action = "career.map"

    def get(self, request, pk):
        job = services.map_job_or_404(request.user, pk)
        return Response(services.job_map(request.user, job))


class NextRoleView(PolicyAPIView):
    policy_action = "career.next_role"

    def get(self, request):
        return Response(services.next_role(request.user))


class InternalJobsView(PolicyAPIView):
    policy_action = "internal.jobs"

    def get(self, request):
        return Response(services.internal_jobs(request.user))


class InternalApplyView(PolicyAPIView):
    policy_action = "internal.apply"
    throttle_classes = [PostOnlyScopedThrottle]
    throttle_scope = "upload"

    def post(self, request, pk):
        application = services.apply_internally(request.user, pk, request=request)
        return Response(
            {"id": str(application.id), "job": application.job.title, "status": application.status},
            status=status.HTTP_201_CREATED,
        )

import uuid
from datetime import date, datetime, time, timedelta

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from applications.models import Application
from applications.services import add_candidate_message
from core.utils import paginate
from core.views import PolicyAPIView
from interviews.timeutil import IST

from . import activity
from .models import HiraAction
from .services import answer


class AskView(PolicyAPIView):
    policy_action = "hira.ask"
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "hira"

    def post(self, request):
        message = str(request.data.get("message", "")).strip()
        if not message:
            return Response({"message": "Type a question."}, status=400)
        if len(message) > 500:
            return Response({"message": "Keep questions under 500 characters."}, status=400)
        user = request.user if request.user.is_authenticated else None
        return Response(answer(message, user))


class MessageRecruiterView(PolicyAPIView):
    policy_action = "hira.message"
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "hira"

    def post(self, request):
        app_id = str(request.data.get("application", "")).strip()
        if not app_id:
            return Response({"application": "Choose an application."}, status=400)
        app = get_object_or_404(Application.objects.select_related("job"), pk=app_id, candidate=request.user)
        add_candidate_message(app, request.user, str(request.data.get("message", "")), request=request)
        return Response(
            {"detail": f"Sent. The recruiter for {app.job.title} will see your message."}, status=201
        )


class BriefingView(PolicyAPIView):
    """HIRA's login briefing for recruiters and hr_admin (counts from the activity log)."""

    policy_actions = {"GET": "hira.briefing", "POST": "hira.briefing"}

    def get(self, request):
        return Response(activity.briefing(request.user))

    def post(self, request):
        activity.mark_seen(request.user)
        return Response({"ok": True})


class ActivityListView(PolicyAPIView):
    policy_action = "hira.activity"

    def get(self, request):
        qs = activity.scoped(request.user)
        params = request.query_params
        if params.get("action") in HiraAction.values:
            qs = qs.filter(action=params["action"])
        if params.get("job"):
            try:
                qs = qs.filter(job_id=uuid.UUID(params["job"]))
            except ValueError:
                return Response({"job": "Unknown job."}, status=400)
        if params.get("needs_you") in ("1", "true"):
            qs = qs.filter(needs_you=True)
        # Dates are IST calendar days.
        for key in ("from", "to"):
            if params.get(key):
                try:
                    day = datetime.combine(date.fromisoformat(params[key]), time(0, 0), tzinfo=IST)
                except ValueError:
                    return Response({key: "Use a date like 2026-11-30."}, status=400)
                if key == "from":
                    qs = qs.filter(created_at__gte=day)
                else:
                    qs = qs.filter(created_at__lt=day + timedelta(days=1))
        return paginate(self, request, qs, activity.row_dict)


class ActivitySummaryView(PolicyAPIView):
    policy_action = "hira.activity"

    def get(self, request):
        try:
            days = min(60, max(7, int(request.query_params.get("days", 14))))
        except ValueError:
            days = 14
        return Response(activity.summary(request.user, days=days))

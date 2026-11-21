from django.conf import settings
from django.http import HttpResponse
from django.utils.html import escape
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import SAFE_METHODS, enforce_csrf
from .permissions import PolicyPermission
from .tasks import run_nightly, run_tick
from .utils import IgnoreClientContentNegotiation


class PolicyAPIView(APIView):
    """Base view: policy permission and CSRF on every unsafe method."""

    permission_classes = [PolicyPermission]
    enforce_csrf = True

    def initial(self, request, *args, **kwargs):
        if self.enforce_csrf and request.method not in SAFE_METHODS:
            enforce_csrf(request)
        super().initial(request, *args, **kwargs)


class PingView(PolicyAPIView):
    """Keep-alive and health check. Must not touch the database."""

    policy_action = "system.ping"
    authentication_classes = []
    throttle_classes = []

    def get(self, request):
        response = Response({"status": "ok"})
        response["Cache-Control"] = "no-store"
        return response


class InternalView(PolicyAPIView):
    authentication_classes = []
    enforce_csrf = False  # machine-to-machine; protected by the secret header


class TickView(InternalView):
    policy_action = "system.tick"

    def post(self, request):
        return Response(run_tick())


class NightlyView(InternalView):
    policy_action = "system.nightly"

    def post(self, request):
        return Response(run_nightly())


class SitemapView(PolicyAPIView):
    policy_action = "seo.sitemap"
    authentication_classes = []
    content_negotiation_class = IgnoreClientContentNegotiation

    def get(self, request):
        from jobs.models import Job

        site = settings.SITE_URL
        rows = [f"<url><loc>{escape(site)}/</loc></url>", f"<url><loc>{escape(site)}/jobs</loc></url>"]
        for slug, updated in Job.objects.open().values_list("slug", "updated_at"):
            rows.append(
                f"<url><loc>{escape(site)}/jobs/{escape(slug)}</loc>"
                f"<lastmod>{updated.date().isoformat()}</lastmod></url>"
            )
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(rows) + "</urlset>"
        )
        return HttpResponse(body, content_type="application/xml; charset=utf-8")


PRIVATE_PREFIXES = (
    "/api/",
    "/candidate",
    "/recruiter",
    "/manager",
    "/employee",
    "/admin",
    "/profile",
    "/notifications",
)


class RobotsView(PolicyAPIView):
    policy_action = "seo.robots"
    authentication_classes = []
    content_negotiation_class = IgnoreClientContentNegotiation

    def get(self, request):
        lines = ["User-agent: *", "Allow: /"]
        lines += [f"Disallow: {prefix}" for prefix in PRIVATE_PREFIXES]
        lines.append(f"Sitemap: {settings.SITE_URL}/sitemap.xml")
        return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")


class AuditListView(PolicyAPIView):
    policy_action = "audit.list"

    def get(self, request):
        from .models import AuditLog
        from .utils import paginate

        qs = AuditLog.objects.select_related("actor")
        action = request.query_params.get("action", "").strip()
        if action:
            qs = qs.filter(action__startswith=action)

        def row(entry):
            return {
                "id": str(entry.id),
                "action": entry.action,
                "actor": entry.actor.email if entry.actor else None,
                "target_type": entry.target_type,
                "target_id": entry.target_id,
                "ip_address": entry.ip_address,
                "meta": entry.meta,
                "created_at": entry.created_at.isoformat(),
            }

        return paginate(self, request, qs, row)

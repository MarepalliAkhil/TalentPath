import csv
import io

from django.http import HttpResponse
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response

from accounts.models import Role
from core.audit import audit
from core.utils import IgnoreClientContentNegotiation
from core.views import PolicyAPIView
from org.models import Department

from . import metrics


def _report(request, name: str) -> list[dict]:
    f = metrics.parse_filters(request.query_params)
    if name == "hiring":
        return metrics.hiring_report(request.user, f)
    if name == "people":
        if request.user.role != Role.HR:
            raise PermissionDenied("People analytics are for HR.")
        return metrics.people_report(f)
    raise NotFound()


class AnalyticsView(PolicyAPIView):
    """GET /api/analytics/<hiring|people>?from=&to=&department="""

    policy_action = "analytics.read"

    def get(self, request, report):
        f = metrics.parse_filters(request.query_params)
        sections = _report(request, report)
        return Response(
            {
                "report": report,
                "from": f.start.isoformat(),
                "to": f.end.isoformat(),
                "department": f.department,
                "scope": "all" if request.user.role == Role.HR else "own",
                "departments": [{"id": str(d.id), "name": d.name} for d in Department.objects.all()],
                "sections": sections,
            }
        )


class AnalyticsExportView(PolicyAPIView):
    """GET /api/analytics/<report>/<section>.csv with the same filters and scope as the page."""

    policy_action = "analytics.read"
    content_negotiation_class = IgnoreClientContentNegotiation

    def get(self, request, report, key):
        sections = {s["key"]: s for s in _report(request, report)}
        sec = sections.get(key)
        if sec is None:
            raise NotFound()
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([c["label"] for c in sec["columns"]])
        for row in sec["rows"]:
            writer.writerow(
                ["" if row.get(c["key"]) is None else _safe(row.get(c["key"])) for c in sec["columns"]]
            )
        audit(request, "analytics.exported", report=report, section=key)
        response = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="talentpath-{report}-{key}.csv"'
        response["Cache-Control"] = "no-store"
        return response


def _safe(value):
    """Stop spreadsheet formula injection: text starting with = + - @ gets a leading quote."""
    text = str(value)
    if isinstance(value, str) and text[:1] in ("=", "+", "-", "@"):
        return "'" + text
    return text

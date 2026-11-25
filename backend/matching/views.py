from rest_framework.response import Response

from applications.blind import known_values
from applications.models import Application
from core.audit import audit
from core.views import PolicyAPIView

from .fairness import check
from .services import get_matcher, job_requirements


class FairnessCheckView(PolicyAPIView):
    """HR: run the counterfactual check on current applications (in memory only)."""

    policy_action = "fairness.check"

    def get(self, request):
        try:
            limit = max(1, min(int(request.query_params.get("limit", 40)), 200))
        except ValueError:
            limit = 40
        apps = list(
            Application.objects.select_related("job__level", "candidate__profile").order_by("created_at")[
                :limit
            ]
        )
        matcher = get_matcher()
        cache = {}

        def items():
            for app in apps:
                if app.job_id not in cache:
                    cache[app.job_id] = job_requirements(app.job, matcher)
                yield app.candidate_code, app.resume_text or "", known_values(app), cache[app.job_id]

        result = check(items(), matcher)
        audit(request, "fairness.check", applications=result.applications, changes=result.changes)
        verdict = (
            f"{result.variants} variants tested, {result.changes} score "
            f"{'change' if result.changes == 1 else 'changes'}."
        )
        return Response(
            {
                "applications": result.applications,
                "variants": result.variants,
                "changes": result.changes,
                "passed": result.changes == 0,
                "summary": verdict,
                "examples": result.examples,
                "changed_fields": ["name", "gender words and pronouns", "college or university", "city"],
            }
        )

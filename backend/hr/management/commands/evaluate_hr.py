"""python manage.py evaluate_hr [--show-misses]

Measures the HR assistant's intent accuracy on hr/eval_data.py (tune and holdout
reported separately). Policy questions also check which source was cited.
Reads the handbook from the database and the default leave types; writes nothing.
"""

from collections import defaultdict
from datetime import date

from django.core.management.base import BaseCommand

from hr.assistant import describe_leave_type, policy_docs, understand
from hr.defaults import DEFAULT_LEAVE_TYPES
from hr.eval_data import QUESTIONS
from hr.models import LeaveType

TODAY = date(2026, 11, 23)  # fixed, so date parsing is repeatable


def default_docs() -> list:
    docs = policy_docs(None)
    for spec in DEFAULT_LEAVE_TYPES:
        lt = LeaveType(**spec)
        docs.append(
            {
                "slug": f"leave-{lt.code}",
                "title": f"{lt.name} policy",
                "keywords": f"{lt.name} {lt.code} leave policy rules",
                "body": describe_leave_type(lt),
                "link": f"/hr/policies#leave-{lt.code}",
            }
        )
    return docs


def evaluate(show_misses=False) -> dict:
    docs = default_docs()
    results = defaultdict(lambda: [0, 0])
    misses = []
    for split, question, expected in QUESTIONS:
        parsed = understand(question, TODAY, docs)
        got = parsed.intent
        if got == "policy" and parsed.policy_hit:
            got = f"policy:{parsed.policy_hit['slug']}"
        ok = got == expected
        results[split][0] += ok
        results[split][1] += 1
        if not ok:
            misses.append((split, question, expected, got))
    return {"results": dict(results), "misses": misses if show_misses else []}


class Command(BaseCommand):
    help = "Measure HR assistant intent accuracy (tune and holdout)."

    def add_arguments(self, parser):
        parser.add_argument("--show-misses", action="store_true")
        parser.add_argument("--split", choices=["tune", "holdout", "all"], default="all")

    def handle(self, *args, **options):
        out = evaluate(show_misses=options["show_misses"])
        for split in ("tune", "holdout"):
            if options["split"] in (split, "all"):
                right, total = out["results"].get(split, [0, 0])
                self.stdout.write(f"{split}: {right}/{total} ({100 * right / max(total, 1):.0f}%)")
        for split, question, expected, got in out["misses"]:
            if options["split"] in (split, "all"):
                self.stdout.write(f"  [{split}] {question!r}: expected {expected}, got {got}")

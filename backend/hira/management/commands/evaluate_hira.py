"""python manage.py evaluate_hira [--split tune|holdout|all] [--verbose]

Measures Ask HIRA's intent accuracy on hira/eval_data.py. A FAQ question counts
as correct only when the right knowledge entry is chosen.
"""

from django.core.management.base import BaseCommand

from hira.engine import understand
from hira.eval_data import QUESTIONS
from hira.services import build_context


def predicted_label(u) -> str:
    return f"faq:{u.faq_key}" if u.intent == "faq" else u.intent


def run(split: str = "all") -> dict:
    ctx = build_context()
    rows = []
    for row_split, question, expected in QUESTIONS:
        if split != "all" and row_split != split:
            continue
        got = predicted_label(understand(question, ctx))
        rows.append((question, expected, got))
    correct = sum(1 for _, e, g in rows if e == g)
    return {"rows": rows, "correct": correct, "total": len(rows)}


class Command(BaseCommand):
    help = "Measure Ask HIRA intent accuracy on the labelled questions."

    def add_arguments(self, parser):
        parser.add_argument("--split", default="all", choices=["tune", "holdout", "all"])
        parser.add_argument("--verbose", action="store_true")

    def handle(self, *args, **options):
        for split in ["tune", "holdout"] if options["split"] == "all" else [options["split"]]:
            report = run(split)
            pct = 100 * report["correct"] / report["total"]
            self.stdout.write(f"{split}: {report['correct']}/{report['total']} intents correct ({pct:.0f}%)")
            if options["verbose"]:
                for question, expected, got in report["rows"]:
                    if expected != got:
                        self.stdout.write(f"  MISS {question!r}: expected {expected}, got {got}")

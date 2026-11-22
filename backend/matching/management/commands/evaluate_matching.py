"""python manage.py evaluate_matching [--split tune|holdout|all]

Scores the 40 hand-labelled pairs in matching/eval_data.py and prints band
accuracy and the confusion between bands. Uses the seeded taxonomy.
"""

from collections import Counter
from datetime import date

from django.core.management.base import BaseCommand

from matching.eval_data import JOBS, PAIRS
from matching.fairness import score_text
from matching.scoring import JobRequirements
from matching.services import get_matcher
from org.models import Skill

BANDS = ["strong", "good", "partial", "low"]


def run(split: str = "all", today: date = date(2026, 11, 21)) -> dict:
    matcher = get_matcher()
    by_name = {s.name: s.slug for s in Skill.objects.all()}
    results = []
    for pair_split, job_key, expected, text in PAIRS:
        if split != "all" and pair_split != split:
            continue
        spec = JOBS[job_key]
        req = JobRequirements(
            required=tuple((by_name[n], n) for n in spec["required"]),
            nice=tuple((by_name[n], n) for n in spec["nice"]),
            level_rank=spec["level"],
        )
        got = score_text(text, req, matcher, today)
        results.append((pair_split, job_key, expected, got.band, got.score))
    correct = sum(1 for r in results if r[2] == r[3])
    confusion = Counter((r[2], r[3]) for r in results)
    return {"results": results, "correct": correct, "total": len(results), "confusion": confusion}


class Command(BaseCommand):
    help = "Measure the fit score against the hand-labelled evaluation pairs."

    def add_arguments(self, parser):
        parser.add_argument("--split", default="all", choices=["tune", "holdout", "all"])
        parser.add_argument("--verbose", action="store_true")

    def handle(self, *args, **options):
        for split in ["tune", "holdout"] if options["split"] == "all" else [options["split"]]:
            report = run(split)
            pct = 100 * report["correct"] / report["total"]
            self.stdout.write(
                f"{split}: {report['correct']}/{report['total']} in the expected band ({pct:.0f}%)"
            )
            header = "expected \\ got " + " ".join(f"{b:>8}" for b in BANDS)
            self.stdout.write(header)
            for exp in BANDS:
                row = " ".join(f"{report['confusion'].get((exp, got), 0):>8}" for got in BANDS)
                self.stdout.write(f"{exp:>14} {row}")
            if options["verbose"]:
                for r in report["results"]:
                    flag = "" if r[2] == r[3] else "  <-- mismatch"
                    self.stdout.write(f"  {r[1]:<9} expected {r[2]:<8} got {r[3]:<8} ({r[4]}){flag}")

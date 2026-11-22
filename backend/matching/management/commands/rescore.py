from django.core.management.base import BaseCommand

from jobs.models import Job
from matching.services import rescore_job
from matching.weights import SCORER_VERSION


class Command(BaseCommand):
    help = "Recompute fit scores for every application (for example after changing matching/weights.py)."

    def handle(self, *args, **options):
        total = sum(rescore_job(job) for job in Job.objects.select_related("level"))
        self.stdout.write(self.style.SUCCESS(f"Re-scored {total} applications (scorer v{SCORER_VERSION})."))

from django.core.management.base import BaseCommand

from applications.models import Application
from matching.services import get_matcher, parse_application, score_application
from matching.weights import EXTRACTOR_VERSION


class Command(BaseCommand):
    help = "Re-parse resumes whose ParsedProfile is older than the current extractor (or --all)."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Re-parse every application.")

    def handle(self, *args, **options):
        matcher = get_matcher()
        qs = Application.objects.select_related("job__level")
        if not options["all"]:
            qs = qs.exclude(parsed_profile__version=EXTRACTOR_VERSION)
        count = 0
        for app in qs.iterator():
            parse_application(app, matcher)
            score_application(app)
            count += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Re-parsed and re-scored {count} applications (extractor v{EXTRACTOR_VERSION})."
            )
        )

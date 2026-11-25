"""python manage.py first_run_free

First start of the free deployment. Run it once from your PC with DATABASE_URL pointing at Neon
(docs/DEPLOY.md, step 2):

1. creates the btree_gist extension the interview exclusion constraint needs (a clear error if the
   database refuses);
2. applies every migration;
3. seeds the demo data only when the database has no accounts yet.

It never resets anything: a database that already has accounts is left exactly as it is.
"""

import os

from django.core.management import BaseCommand, CommandError, call_command
from django.db import DatabaseError, connection

BTREE_GIST_HELP = (
    "Could not create the btree_gist extension ({error}). The interview scheduler needs it for its "
    "no-double-booking constraint. On Neon, open the SQL Editor for this database and run "
    "CREATE EXTENSION IF NOT EXISTS btree_gist; as the database owner, then run this command again."
)


def database_state() -> str:
    """'empty' (no accounts), 'demo' (only *.example demo accounts) or 'real' (anything else)."""
    from accounts.models import User

    if not User.objects.exists():
        return "empty"
    if User.objects.exclude(email__endswith=".example").exists():
        return "real"
    return "demo"


def ensure_btree_gist(conn=connection) -> str:
    if conn.vendor != "postgresql":
        return "skipped (not PostgreSQL)"
    with conn.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_extension WHERE extname = 'btree_gist'")
        if cursor.fetchone():
            return "already installed"
    try:
        with conn.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    except DatabaseError as exc:
        raise CommandError(BTREE_GIST_HELP.format(error=str(exc).strip().splitlines()[0])) from exc
    return "created"


class Command(BaseCommand):
    help = (
        "First run of a free deployment: btree_gist, migrate, and seed the demo only into an empty database."
    )

    def add_arguments(self, parser):
        parser.add_argument("--no-seed", action="store_true", help="Migrate only; never seed.")

    def handle(self, *args, **options):
        settings = connection.settings_dict
        self.stdout.write(f"Database: {settings.get('NAME')} on {settings.get('HOST') or 'localhost'}")
        if os.environ.get("DJANGO_LOAD_DOTENV") != "0":
            self.stdout.write(
                self.style.WARNING(
                    "Warning: backend/.env is being read. Anything you did not set in this window "
                    "(for example FIELD_ENCRYPTION_KEY) comes from your LOCAL .env. Data encrypted with "
                    "local keys cannot be read by the deployed server. For a deployment, set "
                    "DJANGO_LOAD_DOTENV=0 and the production values first (docs/DEPLOY.md, step 2)."
                )
            )

        self.stdout.write(f"btree_gist: {ensure_btree_gist()}")

        call_command("migrate", interactive=False, verbosity=1, stdout=self.stdout)

        state = database_state()
        if options["no_seed"]:
            self.stdout.write("Not seeding (--no-seed).")
        elif state == "empty":
            self.stdout.write(
                "The database has no accounts: seeding the demo data (this takes a minute or two)..."
            )
            call_command("seed", stdout=self.stdout)
        elif state == "demo":
            self.stdout.write(
                "The database already has the demo data: left as it is. "
                "(With DEMO_MODE on, the nightly job rebuilds it.)"
            )
        else:
            self.stdout.write(
                "The database holds accounts that are not demo accounts: nothing was seeded or reset."
            )
        self.stdout.write(self.style.SUCCESS("First run complete."))

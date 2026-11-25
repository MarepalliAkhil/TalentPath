"""Create the first real admin (for production, where demo data is off).

The admin then creates recruiters, HR, managers and employees on the People page.

BOOTSTRAP_ADMIN_PASSWORD=... python manage.py bootstrap_admin --email you@company.com --name "Your Name"
"""

import os

from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Role, User
from accounts.services import create_user


class Command(BaseCommand):
    help = "Create an admin account. Password comes from BOOTSTRAP_ADMIN_PASSWORD."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--name", required=True)

    def handle(self, *args, **options):
        password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "")
        if not password:
            raise CommandError("Set BOOTSTRAP_ADMIN_PASSWORD in the environment.")
        email = options["email"].strip().lower()
        if User.objects.filter(email=email).exists():
            raise CommandError("A user with that email already exists.")
        validate_password(password)
        create_user(email=email, full_name=options["name"], role=Role.ADMIN, password=password)
        self.stdout.write(self.style.SUCCESS(f"Admin {email} created."))

import uuid

import django.db.models.deletion
from django.db import migrations, models

import core.fields


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="User",
            fields=[
                ("password", models.CharField(max_length=128, verbose_name="password")),
                (
                    "last_login",
                    models.DateTimeField(blank=True, null=True, verbose_name="last login"),
                ),
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("full_name", models.CharField(max_length=120)),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("candidate", "Candidate"),
                            ("recruiter", "Recruiter"),
                            ("hiring_manager", "Hiring manager"),
                            ("employee", "Employee"),
                            ("hr_admin", "HR admin"),
                        ],
                        db_index=True,
                        default="candidate",
                        max_length=20,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["full_name"]},
        ),
        migrations.CreateModel(
            name="Profile",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("headline", models.CharField(blank=True, default="", max_length=160)),
                ("location_text", models.CharField(blank=True, default="", max_length=120)),
                ("phone", core.fields.EncryptedTextField(blank=True, default="")),
                (
                    "phone_bidx",
                    models.CharField(blank=True, db_index=True, default="", max_length=64),
                ),
                ("address", core.fields.EncryptedTextField(blank=True, default="")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="profile",
                        to="accounts.user",
                    ),
                ),
            ],
        ),
    ]

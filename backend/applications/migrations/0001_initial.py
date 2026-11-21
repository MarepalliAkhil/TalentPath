import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import core.fields

STATUS_CHOICES = [
    ("applied", "Applied"),
    ("screening", "Screening"),
    ("interview", "Interview"),
    ("offer", "Offer"),
    ("hired", "Hired"),
    ("rejected", "Not selected"),
    ("withdrawn", "Withdrawn"),
]


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("files", "0001_initial"),
        ("jobs", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Application",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=STATUS_CHOICES, db_index=True, default="applied", max_length=20
                    ),
                ),
                ("cover_note", models.TextField(blank=True, default="")),
                ("resume_filename", models.CharField(blank=True, default="", max_length=120)),
                ("resume_text", core.fields.EncryptedTextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "candidate",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="applications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "job",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="applications",
                        to="jobs.job",
                    ),
                ),
                (
                    "resume_file",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="files.storedfile",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("job", "candidate"), name="uniq_application_job_candidate"
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="ApplicationEvent",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("from_status", models.CharField(blank=True, default="", max_length=20)),
                ("to_status", models.CharField(max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "application",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events",
                        to="applications.application",
                    ),
                ),
            ],
            options={"ordering": ["created_at"]},
        ),
    ]

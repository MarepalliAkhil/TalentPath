import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("org", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Job",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("slug", models.SlugField(max_length=140, unique=True)),
                ("title", models.CharField(max_length=120)),
                (
                    "work_mode",
                    models.CharField(
                        choices=[("onsite", "On-site"), ("hybrid", "Hybrid"), ("remote", "Remote")],
                        default="hybrid",
                        max_length=10,
                    ),
                ),
                (
                    "employment_type",
                    models.CharField(
                        choices=[
                            ("full_time", "Full-time"),
                            ("part_time", "Part-time"),
                            ("contract", "Contract"),
                            ("internship", "Internship"),
                        ],
                        default="full_time",
                        max_length=12,
                    ),
                ),
                ("description", models.TextField()),
                ("openings", models.PositiveSmallIntegerField(default=1)),
                (
                    "status",
                    models.CharField(
                        choices=[("draft", "Draft"), ("open", "Open"), ("closed", "Closed")],
                        db_index=True,
                        default="draft",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "department",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="jobs",
                        to="org.department",
                    ),
                ),
                (
                    "location",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="jobs",
                        to="org.location",
                    ),
                ),
                (
                    "level",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="jobs",
                        to="org.joblevel",
                    ),
                ),
                (
                    "required_skills",
                    models.ManyToManyField(
                        blank=True, related_name="jobs_required", to="org.skill"
                    ),
                ),
                (
                    "nice_to_have_skills",
                    models.ManyToManyField(blank=True, related_name="jobs_nice", to="org.skill"),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="jobs_created",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "hiring_manager",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="jobs_managed",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]

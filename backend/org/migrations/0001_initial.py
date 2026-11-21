import uuid

from django.db import migrations, models


def _uuid():
    return models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Department",
            fields=[
                ("id", _uuid()),
                ("name", models.CharField(max_length=100, unique=True)),
                ("slug", models.SlugField(max_length=120, unique=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="Location",
            fields=[
                ("id", _uuid()),
                ("name", models.CharField(max_length=100, unique=True)),
                ("slug", models.SlugField(max_length=120, unique=True)),
                ("country", models.CharField(default="India", max_length=60)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="JobLevel",
            fields=[
                ("id", _uuid()),
                ("name", models.CharField(max_length=60, unique=True)),
                ("rank", models.PositiveSmallIntegerField(unique=True)),
            ],
            options={"ordering": ["rank"]},
        ),
        migrations.CreateModel(
            name="Skill",
            fields=[
                ("id", _uuid()),
                ("name", models.CharField(max_length=80, unique=True)),
                ("slug", models.SlugField(max_length=100, unique=True)),
                (
                    "kind",
                    models.CharField(
                        choices=[("tech", "Tech"), ("non_tech", "Non-tech")],
                        default="tech",
                        max_length=10,
                    ),
                ),
                ("category", models.CharField(blank=True, default="", max_length=60)),
                ("synonyms", models.JSONField(blank=True, default=list)),
            ],
            options={"ordering": ["name"]},
        ),
    ]

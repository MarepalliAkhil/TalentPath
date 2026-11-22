"""Week 2: applications that already reached Interview or later are treated as revealed."""

from django.db import migrations
from django.db.models import F


def forwards(apps, schema_editor):
    Application = apps.get_model("applications", "Application")
    Application.objects.filter(
        status__in=["interview", "offer", "hired"], identity_revealed_at__isnull=True
    ).update(identity_revealed_at=F("updated_at"), reveal_reason="Reached the reveal stage before week 2")


class Migration(migrations.Migration):
    dependencies = [("applications", "0002_application_identity_revealed_at_and_more")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]

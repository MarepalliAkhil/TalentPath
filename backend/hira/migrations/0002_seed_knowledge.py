"""Reference data: Ask HIRA's knowledge entries ship with the schema."""

from django.db import migrations


def seed(apps, schema_editor):
    from hira.knowledge import ENTRIES

    KnowledgeEntry = apps.get_model("hira", "KnowledgeEntry")
    for entry in ENTRIES:
        KnowledgeEntry.objects.update_or_create(key=entry["key"], defaults={k: v for k, v in entry.items() if k != "key"})


class Migration(migrations.Migration):
    dependencies = [("hira", "0001_initial")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]

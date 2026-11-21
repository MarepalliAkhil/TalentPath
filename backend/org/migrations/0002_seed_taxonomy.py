"""Reference data: the skills taxonomy ships with the schema."""

from django.db import migrations


def seed_skills(apps, schema_editor):
    from org.taxonomy_data import SKILLS, skill_slug

    Skill = apps.get_model("org", "Skill")
    for name, kind, category, synonyms in SKILLS:
        Skill.objects.get_or_create(
            slug=skill_slug(name),
            defaults={"name": name, "kind": kind, "category": category, "synonyms": synonyms},
        )


class Migration(migrations.Migration):
    dependencies = [("org", "0001_initial")]

    operations = [migrations.RunPython(seed_skills, migrations.RunPython.noop)]

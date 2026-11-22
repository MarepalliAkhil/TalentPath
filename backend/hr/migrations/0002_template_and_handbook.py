from django.db import migrations


def load(apps, schema_editor):
    from hr.defaults import CHECKLIST_TEMPLATE, HANDBOOK

    Item = apps.get_model("hr", "OnboardingTemplateItem")
    Section = apps.get_model("hr", "HandbookSection")
    for dept, order, title, description, category, owner, kind, offset in CHECKLIST_TEMPLATE:
        Item.objects.get_or_create(
            department_name=dept or "",
            title=title,
            defaults={
                "order": order,
                "description": description,
                "category": category,
                "owner": owner,
                "kind": kind,
                "due_offset_days": offset,
            },
        )
    for n, (slug, title, keywords, body) in enumerate(HANDBOOK):
        Section.objects.update_or_create(
            slug=slug, defaults={"title": title, "keywords": keywords, "body": body, "order": n * 10}
        )


class Migration(migrations.Migration):
    dependencies = [("hr", "0001_initial")]
    operations = [migrations.RunPython(load, migrations.RunPython.noop)]

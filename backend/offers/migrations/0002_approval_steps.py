"""Offer approval steps follow the new role names (D-80): hiring_manager -> manager,
hr_admin -> hr. Reversible; no row is deleted."""

from django.db import migrations, models

STEPS = [("", "None"), ("manager", "Hiring manager"), ("hr", "HR")]


def forwards(apps, schema_editor):
    Offer = apps.get_model("offers", "Offer")
    Offer.objects.filter(approval_step="hiring_manager").update(approval_step="manager")
    Offer.objects.filter(approval_step="hr_admin").update(approval_step="hr")


def backwards(apps, schema_editor):
    Offer = apps.get_model("offers", "Offer")
    Offer.objects.filter(approval_step="manager").update(approval_step="hiring_manager")
    Offer.objects.filter(approval_step="hr").update(approval_step="hr_admin")


class Migration(migrations.Migration):
    dependencies = [("offers", "0001_initial")]

    operations = [
        migrations.RunPython(forwards, backwards),
        migrations.AlterField(
            model_name="offer",
            name="approval_step",
            field=models.CharField(blank=True, choices=STEPS, default="", max_length=20),
        ),
    ]

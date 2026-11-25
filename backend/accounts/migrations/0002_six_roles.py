"""Six roles (D-80): hr_admin becomes hr, hiring_manager becomes manager, and the seeded
admin account becomes the new admin role. No row is deleted; the reverse migration maps
hr and admin back to hr_admin and manager back to hiring_manager."""

from django.db import migrations, models

SEEDED_ADMIN = "admin@demo.example"


def forwards(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(role="hiring_manager").update(role="manager")
    User.objects.filter(role="hr_admin", email__iexact=SEEDED_ADMIN).update(role="admin")
    User.objects.filter(role="hr_admin").update(role="hr")


def backwards(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(role="manager").update(role="hiring_manager")
    User.objects.filter(role__in=["hr", "admin"]).update(role="hr_admin")


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("candidate", "Candidate"),
                    ("recruiter", "Recruiter"),
                    ("manager", "Manager"),
                    ("employee", "Employee"),
                    ("hr", "HR"),
                    ("admin", "Admin"),
                    # Old values stay valid until the data step below has moved every row.
                    ("hiring_manager", "Hiring manager (old)"),
                    ("hr_admin", "HR admin (old)"),
                ],
                db_index=True,
                default="candidate",
                max_length=20,
            ),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("candidate", "Candidate"),
                    ("recruiter", "Recruiter"),
                    ("manager", "Manager"),
                    ("employee", "Employee"),
                    ("hr", "HR"),
                    ("admin", "Admin"),
                ],
                db_index=True,
                default="candidate",
                max_length=20,
            ),
        ),
    ]

"""PostgreSQL exclusion constraint: one person's active claims can never overlap.

Needs the btree_gist extension (a trusted extension on PostgreSQL 13+, available
on Neon). Skipped on other databases (the SQLite scratch runs used while
building); the service layer still checks clashes inside a locked transaction.
"""

from django.db import migrations

CONSTRAINT = "interviews_timeclaim_no_overlap"

FORWARD = [
    "CREATE EXTENSION IF NOT EXISTS btree_gist",
    f"""
    ALTER TABLE interviews_timeclaim
    ADD CONSTRAINT {CONSTRAINT}
    EXCLUDE USING gist (
        person_id WITH =,
        tstzrange(starts_at, ends_at, '[)') WITH &&
    ) WHERE (active)
    """,
]
BACKWARD = [f"ALTER TABLE interviews_timeclaim DROP CONSTRAINT IF EXISTS {CONSTRAINT}"]


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for sql in FORWARD:
        schema_editor.execute(sql)


def backwards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for sql in BACKWARD:
        schema_editor.execute(sql)


class Migration(migrations.Migration):
    dependencies = [("interviews", "0001_initial")]

    operations = [migrations.RunPython(forwards, backwards)]

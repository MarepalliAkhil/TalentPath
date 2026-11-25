"""first_run_free: migrate, btree_gist with a clear error, seed only an empty database, never reset."""

from io import StringIO
from unittest import mock

import pytest
from django.core.management import CommandError, call_command
from django.db import DatabaseError

from accounts.models import Role
from accounts.services import create_user
from seeding.management.commands import first_run_free as cmd


def run(*args):
    calls = []
    real = cmd.call_command

    def fake(name, *a, **kw):
        calls.append(name)
        if name == "migrate":
            return real(name, *a, **kw)
        return None  # never seed or reset for real in these tests

    out = StringIO()
    with mock.patch.object(cmd, "call_command", side_effect=fake):
        call_command("first_run_free", *args, stdout=out)
    return calls, out.getvalue()


@pytest.mark.django_db
def test_empty_database_is_migrated_and_seeded():
    calls, out = run()
    assert calls == ["migrate", "seed"]
    assert "First run complete" in out


@pytest.mark.django_db
def test_demo_database_is_left_alone():
    create_user(
        email="candidate@demo.example", full_name="Demo", role=Role.CANDIDATE, password="Correct-Horse-42!"
    )
    calls, out = run()
    assert calls == ["migrate"] and "left as it is" in out


@pytest.mark.django_db
def test_database_with_real_accounts_is_never_seeded_or_reset():
    create_user(email="hr@company.in", full_name="Real Admin", role=Role.HR, password="Correct-Horse-42!")
    with mock.patch("seeding.management.commands.seed.Command.reset") as reset:
        calls, out = run()
    assert calls == ["migrate"] and "nothing was seeded or reset" in out
    reset.assert_not_called()


@pytest.mark.django_db
def test_no_seed_flag():
    calls, _ = run("--no-seed")
    assert calls == ["migrate"]


def test_btree_gist_refusal_gives_a_clear_error():
    cursor = mock.MagicMock()
    cursor.fetchone.return_value = None
    cursor.execute.side_effect = [None, DatabaseError('permission denied to create extension "btree_gist"')]
    conn = mock.MagicMock(vendor="postgresql")
    conn.cursor.return_value.__enter__.return_value = cursor
    with pytest.raises(CommandError) as err:
        cmd.ensure_btree_gist(conn)
    assert "SQL Editor" in str(err.value) and "permission denied" in str(err.value)


def test_btree_gist_already_installed_or_not_postgres():
    cursor = mock.MagicMock()
    cursor.fetchone.return_value = (1,)
    conn = mock.MagicMock(vendor="postgresql")
    conn.cursor.return_value.__enter__.return_value = cursor
    assert cmd.ensure_btree_gist(conn) == "already installed"
    assert cmd.ensure_btree_gist(mock.MagicMock(vendor="sqlite")) == "skipped (not PostgreSQL)"

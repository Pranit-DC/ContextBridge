"""Reference qualification and safe local maintenance errors."""

import pytest
from sqlalchemy.exc import OperationalError

from contextbridge.engine import related_cli
from contextbridge.engine.related import references


@pytest.mark.parametrize(
    "content,evidence,expected",
    [
        ("Read `db/schema.sql`.", "We read `db/schema.sql`.", ("db/schema.sql",)),
        ("Call `DatabaseConfig`.", "Call `DatabaseConfig`.", ("DatabaseConfig",)),
        ("Use `database`.", "Use `database`.", ()),
        ("Use `db/schema.sql`.", "Use db/schema.sql.", ()),
        ("Use `DB/schema.sql`.", "Use `db/schema.sql`.", ()),
        ("Use ```db/schema.sql```.", "Use ```db/schema.sql```.", ()),
        ("Use `db/schema.sql`.", "A different `api/routes.py`.", ()),
        ("Use `db/schema.sql` with password=private-value.", "Use `db/schema.sql`.", ()),
        ("Use `../db/schema.sql`.", "Use `../db/schema.sql`.", ("../db/schema.sql",)),
    ],
)
def test_only_exact_evidenced_code_references_qualify(content, evidence, expected):
    assert references(content, evidence) == expected


@pytest.mark.parametrize("args", [["--project-id", "x", "--limit", "0"], ["--project-id", " "]])
def test_cli_invalid_settings_are_safe_and_do_not_open_database(args, monkeypatch, capsys):
    def forbidden():
        pytest.fail("Invalid options must fail before loading settings")

    monkeypatch.setattr(related_cli, "Settings", forbidden)
    assert related_cli.main(args) == 1
    assert capsys.readouterr().out == "Related-memory backfill failed: INVALID_INPUT\n"


def test_cli_storage_failure_omits_driver_details(monkeypatch, capsys):
    monkeypatch.setattr(related_cli, "Settings", lambda: object())

    def fail(settings):
        raise OperationalError("private driver details", {}, RuntimeError("private input"))

    monkeypatch.setattr(related_cli, "make_engine", fail)
    assert related_cli.main(["--project-id", "contextbridge"]) == 1
    assert capsys.readouterr().out == "Related-memory backfill failed: STORAGE_UNAVAILABLE\n"

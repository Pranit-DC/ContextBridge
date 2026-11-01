import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text

from tests.integration.write_fakes import Harness

pytestmark = pytest.mark.integration


def test_additive_provenance_migration_preserves_v1_history_and_queued_capture(
    database, monkeypatch
):
    from tests.conftest import TEST_TOKEN

    url, engine = database
    monkeypatch.setenv("CONTEXTBRIDGE_DATABASE_URL", url)
    monkeypatch.setenv("CONTEXTBRIDGE_API_TOKEN", TEST_TOKEN)
    harness = Harness(database)
    harness.process(harness.enqueue()[0])
    _, _, queued = harness.enqueue("Use SQLite.")

    def snapshot():
        with engine.connect() as connection:
            return [
                connection.execute(text(sql)).all()
                for sql in [
                    "SELECT id, current_version, request_fingerprint FROM memories ORDER BY id",
                    "SELECT id, content, evidence, status, valid_from, valid_to "
                    "FROM memory_versions ORDER BY id",
                    "SELECT id, payload, fingerprint, extraction_complete "
                    "FROM capture_events ORDER BY id",
                ]
            ]

    original = snapshot()
    config = Config("alembic.ini")
    try:
        command.downgrade(config, "a25f0138ce41")
        assert snapshot() == original
    finally:
        command.upgrade(config, "head")
    command.check(config)
    assert snapshot() == original
    with harness.client() as client:
        replay = client.post("/v1/interactions", json=queued)
        assert replay.status_code == 202 and replay.json()["status"] == "duplicate"

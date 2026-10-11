import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.orm import Session

from contextbridge.persistence.vectors import vector_available
from tests.conftest import TEST_TOKEN
from tests.integration.write_fakes import Harness

pytestmark = pytest.mark.integration


def test_vector_schema_preserves_p2_claims_relationships_and_capture(database, monkeypatch):
    monkeypatch.setenv("CONTEXTBRIDGE_DATABASE_URL", database[0])
    monkeypatch.setenv("CONTEXTBRIDGE_API_TOKEN", TEST_TOKEN)
    config = Config("alembic.ini")
    harness = Harness(database)
    harness.process(harness.enqueue()[0])
    harness.set_relation("contradiction")
    harness.process(harness.enqueue("Use SQLite.")[0])
    harness.enqueue("Keep database backups.")

    def snapshot():
        with database[1].connect() as connection:
            return [
                connection.execute(text(statement)).all()
                for statement in [
                    "SELECT id, developer_id, claim_key, current_version FROM memories ORDER BY id",
                    "SELECT id, content, evidence, confidence, decision_state "
                    "FROM memory_versions ORDER BY id",
                    "SELECT id, from_version_id, to_version_id, relation "
                    "FROM memory_edges ORDER BY id",
                    "SELECT id, payload, fingerprint, extraction_complete "
                    "FROM capture_events ORDER BY id",
                    "SELECT id, status, reason_codes FROM capture_jobs ORDER BY id",
                    "SELECT candidate_id, payload, admission, plan "
                    "FROM capture_candidates ORDER BY id",
                ]
            ]

    before = snapshot()
    try:
        command.downgrade(config, "36c49ac48101")
        assert snapshot() == before
        command.upgrade(config, "head")
        command.check(config)
        assert snapshot() == before
        if os.getenv("CONTEXTBRIDGE_REQUIRE_VECTOR") == "1":
            with Session(database[1]) as session:
                assert vector_available(session)
    finally:
        command.upgrade(config, "head")

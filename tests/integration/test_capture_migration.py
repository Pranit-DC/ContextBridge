from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from contextbridge.models import CaptureEvent, CaptureJob
from contextbridge.schemas import CreateMemory, UpdateMemory
from contextbridge.service import MemoryService
from tests.conftest import TEST_TOKEN
from tests.integration.write_fakes import Harness
from tests.test_validation import payload

pytestmark = pytest.mark.integration


def test_ingestion_migration_preserves_existing_memory_history_and_replay(database, monkeypatch):
    url, engine = database  # Fixture refuses any database whose name does not end in _test.
    monkeypatch.setenv("CONTEXTBRIDGE_DATABASE_URL", url)
    monkeypatch.setenv("CONTEXTBRIDGE_API_TOKEN", TEST_TOKEN)
    config = Config("alembic.ini")
    original = CreateMemory.model_validate(payload(request_id=str(uuid4())))
    with Session(engine) as session:
        service = MemoryService(session, "migration-owner")
        saved = service.create(original)
        service.update(
            saved.id,
            UpdateMemory(expected_version=1, content="Use SQLite.", source=original.source),
        )
        before = service.inspect(saved.id).model_dump(mode="json")

    def legacy_snapshot():
        with engine.connect() as connection:
            return [
                connection.execute(text(statement)).all()
                for statement in [
                    "SELECT id, scope, project_id, type, current_version, request_fingerprint "
                    "FROM memories ORDER BY id",
                    "SELECT id, memory_id, number, content, status, valid_from, valid_to, evidence "
                    "FROM memory_versions ORDER BY id",
                    "SELECT from_version_id, to_version_id, relation FROM memory_edges ORDER BY id",
                ]
            ]

    legacy = legacy_snapshot()
    command.downgrade(config, "0a67c267d5b4")
    try:
        assert legacy_snapshot() == legacy
        command.upgrade(config, "head")
        command.check(config)
        with Session(engine) as session:
            service = MemoryService(session, "migration-owner")
            assert service.inspect(saved.id).model_dump(mode="json") == before
            replay = service.create(original)
            assert replay.version.number == 1 and replay.current_version == 2
        # Reversing capture/write-engine additions preserves foundation memory/history.
        command.downgrade(config, "0a67c267d5b4")
        assert legacy_snapshot() == legacy
    finally:
        command.upgrade(config, "head")


def test_write_engine_migration_preserves_p1_queued_event_and_replay(database, monkeypatch):
    url, engine = database
    monkeypatch.setenv("CONTEXTBRIDGE_DATABASE_URL", url)
    monkeypatch.setenv("CONTEXTBRIDGE_API_TOKEN", TEST_TOKEN)
    config = Config("alembic.ini")
    harness = Harness(database)
    job_id, _, captured = harness.enqueue()

    def capture_snapshot():
        with engine.connect() as connection:
            return [
                connection.execute(text(statement)).all()
                for statement in [
                    "SELECT id, developer_id, event_id, scope, project_id, payload, fingerprint, "
                    "received_at, expires_at FROM capture_events ORDER BY id",
                    "SELECT id, event_record_id, status, reason_codes, updated_at "
                    "FROM capture_jobs ORDER BY id",
                ]
            ]

    before = capture_snapshot()
    try:
        command.downgrade(config, "24b179ad6c31")
        assert capture_snapshot() == before
        command.upgrade(config, "head")
        command.check(config)
        assert capture_snapshot() == before
        with Session(engine) as session:
            assert session.scalar(select(CaptureEvent)).extraction_complete is False
            assert session.scalar(select(CaptureJob)).retryable is False
        with harness.client() as client:
            replay = client.post("/v1/interactions", json=captured)
            assert replay.status_code == 202
            assert replay.json()["status"] == "duplicate"
            assert replay.json()["job_id"] == job_id
            assert client.get(f"/v1/jobs/{job_id}").json()["status"] == "queued"
    finally:
        command.upgrade(config, "head")

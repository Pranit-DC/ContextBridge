from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from contextbridge.schemas import CreateMemory, UpdateMemory
from contextbridge.service import MemoryService
from tests.conftest import TEST_TOKEN
from tests.test_validation import payload

pytestmark = pytest.mark.integration


def test_ingestion_migration_preserves_existing_memory_history_and_replay(database, monkeypatch):
    url, engine = database  # Fixture refuses any database whose name does not end in _test.
    monkeypatch.setenv("CONTEXTBRIDGE_DATABASE_URL", url)
    monkeypatch.setenv("CONTEXTBRIDGE_API_TOKEN", TEST_TOKEN)
    config = Config("alembic.ini")
    # Use the foundation schema to model an installation with pre-existing memory.
    command.downgrade(config, "0a67c267d5b4")
    try:
        original = CreateMemory.model_validate(payload(request_id=str(uuid4())))
        with Session(engine) as session:
            service = MemoryService(session, "migration-owner")
            saved = service.create(original)
            correction = UpdateMemory(
                expected_version=1, content="Use SQLite.", source=original.source
            )
            service.update(saved.id, correction)
            before = service.inspect(saved.id).model_dump(mode="json")
        command.upgrade(config, "head")
        command.check(config)
        with Session(engine) as session:
            service = MemoryService(session, "migration-owner")
            assert service.inspect(saved.id).model_dump(mode="json") == before
            replay = service.create(original)
            assert replay.version.number == 1 and replay.current_version == 2
        # Reversing only P1 must also preserve the foundation's memory/history.
        command.downgrade(config, "0a67c267d5b4")
        with Session(engine) as session:
            assert (
                MemoryService(session, "migration-owner").inspect(saved.id).model_dump(mode="json")
                == before
            )
    finally:
        command.upgrade(config, "head")

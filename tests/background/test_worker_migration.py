import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from contextbridge.background.runner import WorkRunner
from contextbridge.db import make_session_factory
from contextbridge.models import WorkItem
from tests.integration.retrieval_fakes import create, index
from tests.integration.write_fakes import Harness

pytestmark = pytest.mark.integration


def test_worker_migration_preserves_p3_vectors_and_recovers_accepted_jobs(database, monkeypatch):
    from tests.conftest import TEST_TOKEN

    monkeypatch.setenv("CONTEXTBRIDGE_DATABASE_URL", database[0])
    monkeypatch.setenv("CONTEXTBRIDGE_API_TOKEN", TEST_TOKEN)
    harness = Harness(database)
    pending, _, _ = harness.enqueue()
    memory = create(database)
    index(database, [memory], [[1.0, 0.0]])

    def snapshot():
        with database[1].connect() as db:
            return [
                db.execute(text(sql)).all()
                for sql in [
                    "SELECT id, request_fingerprint, current_version FROM memories ORDER BY id",
                    "SELECT id, content, evidence FROM memory_versions ORDER BY id",
                    "SELECT version_id, model_id, vector "
                    "FROM memory_embeddings ORDER BY version_id",
                    "SELECT id, payload, fingerprint FROM capture_events ORDER BY id",
                    "SELECT id, status FROM capture_jobs ORDER BY id",
                    "SELECT id, status, model_id, dimensions FROM reindex_jobs ORDER BY id",
                ]
            ]

    before = snapshot()
    config = Config("alembic.ini")
    try:
        command.downgrade(config, "70693e8576e5")
        assert snapshot() == before
        command.upgrade(config, "head")
        command.check(config)
        assert snapshot() == before
        WorkRunner(make_session_factory(database[1]), harness.settings, None).backfill()
        with Session(database[1]) as db:
            items = db.scalars(select(WorkItem)).all()
            assert len(items) == 1 and str(items[0].job_id) == pending
    finally:
        command.upgrade(config, "head")

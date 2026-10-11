from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from contextbridge.background.maintenance import maintain
from contextbridge.background.outbox import FenceLost, check_fence
from contextbridge.background.runner import WorkRunner
from contextbridge.background.runtime import WorkerProviders
from contextbridge.db import make_session_factory
from contextbridge.engine.modules import ModuleGateway
from contextbridge.engine.write import WriteEngine
from contextbridge.models import CaptureEvent, CaptureJob, Memory, MemoryVersion, WorkItem
from contextbridge.service import MemoryService
from tests.integration.retrieval_fakes import create
from tests.integration.write_fakes import Harness

pytestmark = pytest.mark.integration


def runner(database, harness, modules=None):
    return WorkRunner(
        make_session_factory(database[1]),
        harness.settings,
        WorkerProviders(modules or harness.modules),
    )


def work_id(database, job_id):
    with Session(database[1]) as session:
        return session.scalar(select(WorkItem.id).where(WorkItem.job_id == UUID(str(job_id))))


def due(database, item_id):
    with database[1].begin() as db:
        db.execute(
            update(WorkItem)
            .where(WorkItem.id == item_id)
            .values(available_at=datetime.now(UTC) - timedelta(seconds=1), published_at=None)
        )


def test_outbox_replay_and_concurrent_delivery_mutate_once(database):
    harness = Harness(database)
    job, _, _ = harness.enqueue()
    item = work_id(database, job)
    worker = runner(database, harness)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(worker.run, [item, item]))
    worker.run(item)
    with Session(database[1]) as session:
        assert session.scalar(select(func.count()).select_from(Memory)) == 1
        assert session.scalar(select(func.count()).select_from(MemoryVersion)) == 1
        row = session.get(WorkItem, item)
        assert row.status == "succeeded" and row.attempts == 1
        assert len(harness.extractor.calls) == 1


def test_committed_domain_job_recovers_after_worker_lost_before_ack(database):
    harness = Harness(database)
    job, _, _ = harness.enqueue()
    item = work_id(database, job)
    worker = runner(database, harness)
    token, _, _ = worker.claim(item)
    with Session(database[1], expire_on_commit=False) as session:
        WriteEngine(
            session,
            harness.settings,
            harness.modules,
            commit_guard=lambda db: check_fence(db, item, token),
        ).process(UUID(job))
    # A fresh process gets redelivery without a previous execution's completion call.
    runner(database, harness).run(item)
    assert worker.inspect(item)["status"] == "succeeded"
    with Session(database[1]) as session:
        assert session.scalar(select(func.count()).select_from(MemoryVersion)) == 1


def test_broker_failure_keeps_outbox_without_spending_provider_attempt(database):
    harness = Harness(database)
    job, _, _ = harness.enqueue()
    item = work_id(database, job)
    worker = runner(database, harness)

    def unavailable(item_id):
        raise ConnectionError("private diagnostic")

    assert worker.dispatch(unavailable) == 0
    assert worker.inspect(item)["attempts"] == 0
    due(database, item)
    messages = []
    assert worker.dispatch(messages.append) == 1
    assert messages == [str(item)]
    worker.run(messages[0])
    assert worker.inspect(item)["status"] == "succeeded"


def test_transient_failure_exhausts_bounded_attempts_and_omits_private_text(database, caplog):
    harness = Harness(database, worker_max_attempts=2, worker_retry_seconds=1)
    job, _, _ = harness.enqueue()
    item = work_id(database, job)

    class Timeout:
        def extract(self, event):
            raise TimeoutError("private conversation secret")

    worker = runner(database, harness, ModuleGateway(extractor=Timeout()))
    worker.run(item)
    assert worker.inspect(item)["status"] == "queued"
    worker.run(item)  # Redelivery cannot bypass backoff.
    assert worker.inspect(item)["attempts"] == 1
    due(database, item)
    worker.run(item)
    assert worker.inspect(item)["status"] == "failed"
    worker.run(item)
    assert worker.inspect(item)["attempts"] == 2
    assert "private conversation" not in caplog.text
    with Session(database[1]) as session:
        job = session.get(CaptureJob, UUID(job))
        assert not job.retryable and job.reason_codes == ["PROVIDER_UNAVAILABLE"]


def test_expired_execution_lease_cannot_save_late_extraction(database):
    harness = Harness(database)
    job, _, _ = harness.enqueue()
    item = work_id(database, job)
    worker = runner(database, harness)
    token, _, _ = worker.claim(item)
    with database[1].begin() as db:
        db.execute(
            update(WorkItem)
            .where(WorkItem.id == item)
            .values(lease_until=datetime.now(UTC) - timedelta(seconds=1))
        )
    new_token, _, _ = worker.claim(item)
    assert new_token != token
    with Session(database[1]) as session, pytest.raises(FenceLost):
        WriteEngine(
            session,
            harness.settings,
            harness.modules,
            commit_guard=lambda db: check_fence(db, item, token),
        ).process(UUID(job))
    with Session(database[1]) as session:
        assert not session.scalar(select(CaptureEvent.extraction_complete))


def test_forget_during_uninterpreted_extraction_cancels_scope_and_redelivery(database):
    harness = Harness(database)
    stored = create(database)
    job, _, _ = harness.enqueue()
    other = Harness(database, project="other-project")
    other_job, _, _ = other.enqueue()
    foreign = Harness(database, owner="developer-b")
    foreign_job, _, _ = foreign.enqueue()

    class Forget:
        def extract(self, event):
            with Session(database[1]) as db:
                MemoryService(db, "developer-a").forget(stored.id)
            return harness.extractor.extract(event)

    worker = runner(
        database, harness, ModuleGateway(extractor=Forget(), admission=harness.modules.admission)
    )
    item = work_id(database, job)
    worker.run(item)
    worker.run(item)
    assert worker.inspect(item)["status"] == "cancelled"
    assert runner(database, other).inspect(work_id(database, other_job))["status"] == "queued"
    assert runner(database, foreign).inspect(work_id(database, foreign_job))["status"] == "queued"
    with Session(database[1]) as session:
        assert session.scalar(select(func.count()).select_from(Memory)) == 0
        assert session.get(CaptureJob, UUID(job)).status == "cancelled"
        event = session.get(CaptureEvent, session.get(CaptureJob, UUID(job)).event_record_id)
        assert event.payload is event.fingerprint is None


def test_recovery_backfills_old_jobs_and_diagnostics_expire(database):
    harness = Harness(database, worker_diagnostic_retention_seconds=60)
    job, _, _ = harness.enqueue()
    with database[1].begin() as db:
        db.execute(delete(WorkItem))
    worker = runner(database, harness)
    worker.backfill()
    item = work_id(database, job)
    worker.run(item)
    with database[1].begin() as db:
        db.execute(update(WorkItem).values(updated_at=datetime.now(UTC) - timedelta(minutes=2)))
    maintain(worker)
    worker.backfill()
    with Session(database[1]) as session:
        assert session.scalar(select(WorkItem)) is None
        assert session.get(CaptureJob, UUID(job)).status == "succeeded"


def test_worker_diagnostics_are_authenticated_and_bound(database):
    harness = Harness(database)
    job, _, _ = harness.enqueue()
    item = work_id(database, job)
    with harness.client() as client:
        response = client.get(f"/v1/worker/jobs/{item}")
        assert response.status_code == 200 and response.json()["attempts"] == 0
        assert "payload" not in response.json()
        assert (
            client.get(f"/v1/worker/jobs/{item}", headers={"Authorization": ""}).status_code == 401
        )
    for foreign in [Harness(database, owner="developer-b"), Harness(database, project="other")]:
        with foreign.client() as client:
            assert client.get(f"/v1/worker/jobs/{item}").status_code == 404

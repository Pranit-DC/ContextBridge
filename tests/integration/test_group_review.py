"""Recovery and erasure regressions for the merged Phase 2 grouping implementation."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from contextbridge.engine.grouping import aggregate, distribute, members
from contextbridge.engine.modules import ModuleGateway
from contextbridge.engine.write import WriteEngine
from contextbridge.models import CaptureEvent, CaptureJob, Memory, WorkItem
from contextbridge.service import MemoryService
from tests.background.test_work import due, runner, work_id
from tests.integration.test_session_groups import enqueue, setup
from tests.integration.write_fakes import Admit, Harness


class RetryFollower(Admit):
    def __init__(self, *, always=False):
        super().__init__()
        self.calls = 0
        self.always = always

    def assess(self, candidate, context):
        if candidate["content"] == "Second database claim.":
            self.calls += 1
            if self.always or self.calls == 1:
                raise TimeoutError("synthetic provider timeout")
        return super().assess(candidate, context)


@pytest.mark.parametrize("always", [False, True])
def test_follower_transient_failure_retries_without_changing_finished_leader(database, always):
    harness, extractor, _ = setup(database, capture_group_max_events=2, worker_max_attempts=2)
    admission = RetryFollower(always=always)
    modules = ModuleGateway(extractor=extractor, admission=admission)
    worker = runner(database, harness, modules)
    first, _ = enqueue(harness, text="First database claim.")
    second, _ = enqueue(harness, text="Second database claim.")
    item = work_id(database, first)
    worker.run(item)
    assert worker.inspect(item)["status"] == "queued"
    with Session(database[1]) as db:
        assert db.get(CaptureJob, first).status == "succeeded"
        assert db.get(CaptureJob, second).retryable is True
    due(database, item)
    runner(database, harness, modules).run(item)
    assert worker.inspect(item)["status"] == ("failed" if always else "succeeded")
    assert worker.inspect(item)["attempts"] == 2
    with Session(database[1]) as db:
        assert db.get(CaptureJob, first).status == "succeeded"
        assert db.get(CaptureJob, second).status == ("failed" if always else "succeeded")
        assert db.scalar(select(func.count()).select_from(Memory)) == (1 if always else 2)
    assert len(extractor.calls) == 1


def freeze_and_finish_first(database, harness, worker, first, *, defer=False):
    item = work_id(database, first)
    assert worker.claim(item) is not None
    with Session(database[1], expire_on_commit=False) as db:
        engine = WriteEngine(db, harness.settings, worker.providers.modules)
        job, event = engine.live_job(first)
        group = members(engine.ingestion, job, event)
        captured, mapping = aggregate(group)
        candidates, _ = distribute(engine.modules.extract(captured), mapping, group)
        for identifier, values in candidates.items():
            engine.save_extraction(identifier, values, commit=False)
        if defer:
            job.reason_codes = ["AMBIGUOUS_TIME"]
        db.commit()
        engine._process_one(first)
        db.execute(
            update(WorkItem)
            .where(WorkItem.id == item)
            .values(lease_until=datetime.now(UTC) - timedelta(seconds=1))
        )
        db.commit()
    return item


@pytest.mark.parametrize("defer", [False, True])
@pytest.mark.parametrize("delivery", ["worker", "engine"])
def test_restart_finishes_pending_group_after_terminal_leader_and_inspection(
    database, defer, delivery
):
    harness, extractor, worker = setup(database, capture_group_max_events=2)
    first, _ = enqueue(harness, text="First database claim.")
    second, _ = enqueue(harness, text="Second database claim.")
    item = freeze_and_finish_first(database, harness, worker, first, defer=defer)
    worker.inspect(item)  # Diagnostics must not rewrite the original source job's outcome.
    with Session(database[1]) as db:
        assert db.get(CaptureJob, first).status == ("deferred" if defer else "succeeded")
    if delivery == "worker":
        runner(database, harness, worker.providers.modules).run(item)
    else:
        with Session(database[1]) as db:
            WriteEngine(db, harness.settings, worker.providers.modules).process(first)
    with Session(database[1]) as db:
        assert db.get(CaptureJob, second).status == "succeeded"
    assert worker.inspect(item)["status"] == ("deferred" if defer else "succeeded")
    assert len(extractor.calls) == 1


@pytest.mark.parametrize("saved", [False, True])
def test_enabling_grouping_preserves_recovery_of_existing_independent_jobs(database, saved):
    harness = Harness(database, worker_retry_seconds=1)
    first, _, event = harness.enqueue()
    item = work_id(database, first)
    if saved:
        from contextbridge.contracts import CapturedEvent

        with Session(database[1]) as db:
            WriteEngine(db, harness.settings, harness.modules).save_extraction(
                UUID(first), harness.modules.extract(CapturedEvent.model_validate(event))
            )
    else:

        class Timeout:
            def extract(self, event):
                raise TimeoutError("synthetic timeout")

        runner(database, harness, ModuleGateway(extractor=Timeout())).run(item)
        due(database, item)
    harness.settings = harness.settings.model_copy(update={"capture_grouping_enabled": True})
    worker = runner(database, harness)
    worker.run(item)
    assert worker.inspect(item)["status"] == "succeeded"
    with Session(database[1]) as db:
        assert db.scalar(select(func.count()).select_from(Memory)) == 1


def test_forget_after_first_group_member_commit_blocks_pending_members(database):
    harness, extractor, worker = setup(database, capture_group_max_events=2)
    first, _ = enqueue(harness, text="First database claim.")
    second, _ = enqueue(harness, text="Second database claim.")
    item = freeze_and_finish_first(database, harness, worker, first)
    with Session(database[1]) as db:
        memory_id = db.scalar(select(Memory.id))
        MemoryService(db, harness.settings.developer_id).forget(memory_id)
    worker.run(item)
    with Session(database[1]) as db:
        assert db.get(CaptureJob, second).status == "cancelled"
        assert db.scalar(select(func.count()).select_from(Memory)) == 0
        assert not db.scalars(select(CaptureEvent).where(CaptureEvent.payload.is_not(None))).all()
    assert len(extractor.calls) == 1


def test_retry_preserves_unresolved_time_reason_alongside_supported_claim(database):
    class TimeoutOnce(Admit):
        calls = 0

        def assess(self, candidate, context):
            self.calls += 1
            if self.calls == 1:
                raise TimeoutError("synthetic timeout")
            return super().assess(candidate, context)

    harness = Harness(database, capture_source_timezone="UTC")
    job, candidate, event = harness.enqueue("Switched SQLite yesterday. Pin Python 3.12.")
    clear = deepcopy(candidate)
    clear.update(candidate_id=str(uuid4()), content="Pin Python 3.12.", claim_key=None)
    clear["source"]["evidence"] = clear["content"]
    harness.extractor.outputs[event["event_id"]] = [candidate, clear]
    worker = runner(
        database, harness, ModuleGateway(extractor=harness.extractor, admission=TimeoutOnce())
    )
    item = work_id(database, job)
    worker.run(item)
    assert worker.inspect(item)["status"] == "queued"
    due(database, item)
    worker.run(item)
    assert worker.inspect(item)["status"] == "deferred"
    with Session(database[1]) as db:
        assert "AMBIGUOUS_TIME" in db.get(CaptureJob, UUID(job)).reason_codes
        assert db.scalar(select(func.count()).select_from(Memory)) == 1

"""Real PostgreSQL/worker mechanics with a deterministic injected extractor, no hosted calls."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from contextbridge.contracts import CapturedEvent
from contextbridge.engine.grouping import ReadinessPolicy
from contextbridge.engine.ingestion import IngestionService
from contextbridge.engine.modules import ModuleGateway
from contextbridge.models import CaptureCandidate, CaptureEvent, CaptureJob, Memory, MemoryVersion
from contextbridge.service import MemoryService
from tests.background.test_work import runner, work_id
from tests.engine.fakes import fixture
from tests.integration.retrieval_fakes import create
from tests.integration.write_fakes import Harness

pytestmark = pytest.mark.integration


class Extract:
    def __init__(self, callback=None):
        self.calls = []
        self.callback = callback

    def extract(self, event):
        self.calls.append(event)
        if self.callback:
            self.callback()
        output = []
        for message in event["messages"]:
            candidate = fixture("candidate")
            candidate.update(
                candidate_id=str(uuid4()),
                event_id=event["event_id"],
                project_id=event["project_id"],
                content=message["content"],
                valid_from=event["occurred_at"],
                claim_key=None,
            )
            candidate["source"].update(
                agent=event["agent"],
                session=event["session"],
                interaction=event["interaction"],
                evidence=message["content"],
            )
            candidate["evidence_refs"] = [
                {"event_id": event["event_id"], "message_id": message["message_id"]}
            ]
            output.append(candidate)
        return output


def enqueue(harness, *, session="session", text="Use SQLite.", messages=1):
    event = fixture("captured-event")
    event.update(
        event_id=str(uuid4()),
        session=session,
        interaction=str(uuid4()),
        project_id=harness.settings.capture_project_id,
        occurred_at=(datetime.now(UTC) - timedelta(days=1)).isoformat(),
        messages=[
            {"message_id": f"m{i}", "role": "user", "content": text} for i in range(messages)
        ],
    )
    with Session(harness.database[1], expire_on_commit=False) as db:
        result = IngestionService(db, harness.settings).ingest(CapturedEvent.model_validate(event))
    return result.job_id, event


def setup(database, **kwargs):
    harness = Harness(database, capture_grouping_enabled=True, **kwargs)
    extractor = Extract()
    modules = ModuleGateway(extractor=extractor, admission=harness.modules.admission)
    return harness, extractor, runner(database, harness, modules)


def test_partial_threshold_order_identity_replay_and_call_comparison(database):
    harness, extractor, worker = setup(database, capture_group_max_events=3)
    jobs = [enqueue(harness, text=f"Use SQLite option {i}.") for i in range(2)]
    worker.run(work_id(database, jobs[0][0]))
    assert extractor.calls == []
    jobs.append(enqueue(harness, text="Use SQLite option 2."))
    # Readiness has not consumed a lease attempt; a fresh runner survives restart.
    worker = runner(database, harness, worker.providers.modules)
    with Session(database[1]) as db:
        from contextbridge.models import WorkItem

        db.execute(update(WorkItem).values(available_at=datetime.now(UTC)))
        db.commit()
    worker.run(work_id(database, jobs[0][0]))
    for job, event in jobs:
        worker.run(work_id(database, job))
        with Session(database[1], expire_on_commit=False) as db:
            assert (
                IngestionService(db, harness.settings)
                .ingest(CapturedEvent.model_validate(event))
                .status
                == "duplicate"
            )
            saved = db.scalar(select(CaptureCandidate).where(CaptureCandidate.job_id == job))
            assert saved.payload["event_id"] == event["event_id"]
            assert saved.payload["evidence_refs"][0]["message_id"] == "m0"
            assert saved.payload["source"]["interaction"] == event["interaction"]
            assert db.get(CaptureJob, job).status == "succeeded"
    assert len(extractor.calls) == 1  # Three per-message calls become one batch call.
    assert [m["content"] for m in extractor.calls[0]["messages"]] == [
        event["messages"][0]["content"] for _, event in jobs
    ]
    with Session(database[1]) as db:
        assert db.scalar(select(func.count()).select_from(Memory)) == 3


def test_idle_restart_and_concurrent_delivery(database):
    harness, extractor, worker = setup(database)
    job, _ = enqueue(harness)
    with database[1].begin() as db:
        db.execute(
            update(CaptureEvent).values(received_at=datetime.now(UTC) - timedelta(seconds=40))
        )
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(worker.run, [work_id(database, job)] * 2))
    assert len(extractor.calls) == 1


def test_sessions_projects_and_owners_are_partitioned(database):
    harness, extractor, worker = setup(database, capture_group_max_events=2)
    first, _ = enqueue(harness)
    enqueue(harness, session="other")
    other = Harness(database, project="elsewhere", capture_grouping_enabled=True)
    enqueue(other)
    enqueue(Harness(database, owner="developer-b", capture_grouping_enabled=True))
    worker.run(work_id(database, first))
    assert not extractor.calls
    enqueue(harness)
    with database[1].begin() as db:
        from contextbridge.models import WorkItem

        db.execute(update(WorkItem).values(available_at=datetime.now(UTC)))
    worker.run(work_id(database, first))
    assert len(extractor.calls) == 1 and len(extractor.calls[0]["messages"]) == 2


@pytest.mark.parametrize("during", ["forget", "expiry"])
def test_deletion_or_expiry_during_group_extraction_cannot_commit(database, during):
    harness, extractor, worker = setup(database, capture_group_max_events=2)
    saved = create(database)
    first, _ = enqueue(harness)
    second, _ = enqueue(harness)

    def cancel():
        with Session(database[1]) as db:
            if during == "forget":
                MemoryService(db, "developer-a").forget(saved.id)
            else:
                db.execute(
                    update(CaptureEvent)
                    .where(CaptureEvent.event_id == UUID(extractor.calls[0]["event_id"]))
                    .values(
                        received_at=datetime.now(UTC) - timedelta(days=2),
                        expires_at=datetime.now(UTC) - timedelta(days=1),
                    )
                )
                db.commit()

    extractor.callback = cancel
    worker.run(work_id(database, first))
    worker.run(work_id(database, second))
    with Session(database[1]) as db:
        assert db.scalar(select(func.count()).select_from(MemoryVersion)) == (during == "expiry")
        assert not db.scalars(
            select(CaptureCandidate).where(CaptureCandidate.payload.is_not(None))
        ).all()


def test_arrival_during_frozen_group_goes_to_next_group(database):
    harness, extractor, worker = setup(database, capture_group_max_events=2)
    first, _ = enqueue(harness)
    enqueue(harness)
    later = []
    extractor.callback = lambda: later.append(enqueue(harness)[0])
    worker.run(work_id(database, first))
    assert len(extractor.calls[0]["messages"]) == 2
    with Session(database[1]) as db:
        assert db.get(CaptureJob, later[0]).group_leader_id is None


@pytest.mark.parametrize(
    "settings,messages",
    [
        ({"capture_group_max_messages": 2}, 2),
        ({"capture_group_max_characters": 5}, 1),
    ],
)
def test_message_and_size_readiness(database, settings, messages):
    harness, extractor, worker = setup(database, **settings)
    job, _ = enqueue(harness, messages=messages)
    worker.run(work_id(database, job))
    assert len(extractor.calls) == 1


def test_policy_bounds():
    with pytest.raises(ValueError):
        ReadinessPolicy(max_events=21)


def test_concurrent_arrivals_are_assigned_once_with_all_source_identities(database):
    harness, extractor, worker = setup(database, capture_group_max_events=2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = list(pool.map(lambda i: enqueue(harness, text=f"Database option {i}."), range(2)))
    for job, _ in jobs:
        worker.run(work_id(database, job))
    assert len(extractor.calls) == 1
    with Session(database[1]) as db:
        group = db.scalars(select(CaptureJob.group_leader_id)).all()
        assert len(set(group)) == 1 and group[0] is not None


def test_expiry_cancels_all_frozen_context_before_provider_execution(database):
    harness, extractor, worker = setup(database, capture_group_max_events=2)
    first, _ = enqueue(harness)
    second, _ = enqueue(harness)
    assert worker.claim(work_id(database, first)) is not None
    with Session(database[1]) as db:
        event_id = db.get(CaptureJob, first).event_record_id
        db.execute(
            update(CaptureEvent)
            .where(CaptureEvent.id == event_id)
            .values(
                received_at=datetime.now(UTC) - timedelta(days=2),
                expires_at=datetime.now(UTC) - timedelta(days=1),
            )
        )
        db.commit()
        IngestionService(db, harness.settings).expire()
        assert db.get(CaptureJob, first).status == "cancelled"
        assert db.get(CaptureJob, second).status == "cancelled"
        assert all(event.payload is None for event in db.scalars(select(CaptureEvent)))
    worker.run(work_id(database, second))
    assert extractor.calls == []


def test_restart_after_first_member_commit_finishes_remaining_without_reextracting(database):
    from contextbridge.engine.grouping import aggregate, distribute, members
    from contextbridge.engine.write import WriteEngine
    from contextbridge.models import WorkItem

    harness, extractor, worker = setup(database, capture_group_max_events=2)
    first, _ = enqueue(harness)
    second, _ = enqueue(harness)
    item = work_id(database, first)
    assert worker.claim(item) is not None
    with Session(database[1], expire_on_commit=False) as db:
        engine = WriteEngine(db, harness.settings, worker.providers.modules)
        job, event = engine.live_job(first)
        group = members(engine.ingestion, job, event)
        captured, mapping = aggregate(group)
        results, _ = distribute(engine.modules.extract(captured), mapping, group)
        for identifier, candidates in results.items():
            engine.save_extraction(identifier, candidates, commit=False)
        db.commit()
        engine._process_one(first)  # Simulate process loss immediately after this commit.
        db.execute(
            update(WorkItem)
            .where(WorkItem.id == item)
            .values(lease_until=datetime.now(UTC) - timedelta(seconds=1))
        )
        db.commit()
    worker.run(item)
    assert len(extractor.calls) == 1
    with Session(database[1]) as db:
        assert db.get(CaptureJob, second).status == "succeeded"
        assert db.scalar(select(func.count()).select_from(Memory)) == 1  # Exact duplicate NOOP.

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from contextbridge.db import make_session_factory
from contextbridge.engine.consolidation_queue import schedule, submit
from contextbridge.engine.errors import EngineError
from contextbridge.management import ConsolidationRequest, RetireMemory
from contextbridge.models import ConsolidationJob, ConsolidationSource, WorkItem
from contextbridge.service import MemoryService
from tests.background.test_consolidation import Proposals, process, setup
from tests.integration.retrieval_fakes import create
from tests.integration.write_fakes import Harness

pytestmark = pytest.mark.integration


def configuration(database):
    return Harness(
        database, consolidation_enabled=True, worker_factory="tests.background.worker_factory:build"
    ).settings


def test_scheduler_serializes_parallel_dispatchers_caps_batch_and_survives_restart(database):
    settings = configuration(database)
    for i in range(23):
        create(database, f"Synthetic fact {i}.")
    create(database, owner="other-developer")
    create(database, project_id="other-project")
    sessions = make_session_factory(database[1])
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: schedule(sessions, settings), range(2))) == [0, 1]
    assert schedule(sessions, settings) == 0
    with Session(database[1]) as db:
        assert db.scalar(select(func.count()).select_from(ConsolidationSource)) == 20
        assert db.scalar(select(func.count()).select_from(WorkItem)) == 1
        job = db.scalar(select(ConsolidationJob))
        assert job.scope == "project" and job.project_id == "contextbridge"
    # An unchanged selection is not reinterpreted after the interval or a process restart.
    assert schedule(sessions, settings, now=datetime.now(UTC) + timedelta(minutes=16)) == 0


def test_condition_buckets_skip_sparse_and_unchanged_sets_but_obey_interval(database):
    settings = configuration(database)
    sessions = make_session_factory(database[1])
    create(database, conditions={"environment": "a-sparse"})
    for _ in range(2):
        create(database, conditions={"environment": "b-production"})
    assert schedule(sessions, settings) == 1
    for _ in range(2):
        create(database, conditions={"environment": "c-test"})
    assert schedule(sessions, settings) == 0
    later = datetime.now(UTC) + timedelta(minutes=16)
    assert schedule(sessions, settings, now=later) == 1
    with Session(database[1]) as db:
        jobs = list(db.scalars(select(ConsolidationJob)))
        assert len(jobs) == 2
        assert {j.conditions["environment"] for j in jobs} == {"b-production", "c-test"}
        assert db.scalar(select(func.count()).select_from(ConsolidationSource)) == 4


def test_manual_submission_checks_scope_current_versions_and_coalesces_scheduler(database):
    settings = configuration(database)
    a, b = create(database), create(database)
    foreign = create(database, project_id="other-project")
    payload = ConsolidationRequest(scope="project", project_id="contextbridge")
    with Session(database[1]) as db:
        with pytest.raises(EngineError, match="OUT_OF_SCOPE"):
            submit(db, settings, payload.model_copy(update={"project_id": "other-project"}))
        db.rollback()
        with pytest.raises(EngineError, match="VERSION_CONFLICT"):
            submit(
                db,
                settings,
                payload.model_copy(update={"version_ids": [a.version.id, foreign.version.id]}),
            )
        db.rollback()
        first = submit(db, settings, payload)
        second = submit(
            db, settings, payload.model_copy(update={"version_ids": [b.version.id, a.version.id]})
        )
        assert first.job_id == second.job_id and first.work_id == second.work_id
        assert first.source_count == 2
        db.execute(
            update(ConsolidationJob).values(updated_at=datetime.now(UTC) - timedelta(hours=1))
        )
        db.commit()
    assert schedule(make_session_factory(database[1]), settings) == 0


def test_generated_contested_retired_and_other_conditions_never_enter_batch(database):
    harness, sources, job = setup(database)
    summary = process(database, harness, job, Proposals())["memory_ids"][0]
    retired = create(database)
    contested = create(database)
    from contextbridge.models import MemoryVersion

    with Session(database[1]) as db:
        MemoryService(db, "developer-a").retire(
            retired.id,
            RetireMemory(scope="project", project_id="contextbridge", expected_version=1),
        )
        db.get(MemoryVersion, contested.version.id).decision_state = "contested"
        db.commit()
    create(database, conditions={"environment": "test"})
    settings = configuration(database)
    with Session(database[1]) as db:
        result = submit(
            db, settings, ConsolidationRequest(scope="project", project_id="contextbridge")
        )
        ids = set(
            db.scalars(
                select(ConsolidationSource.version_id).where(
                    ConsolidationSource.job_id == result.job_id
                )
            )
        )
        assert ids == {s.version.id for s in sources}
        assert summary not in {str(i) for i in ids}
    assert (
        schedule(
            make_session_factory(database[1]),
            settings.model_copy(update={"consolidation_enabled": False}),
        )
        == 0
    )


def test_api_submission_status_is_scoped_and_unconfigured_is_explicit(client):
    for _ in range(2):
        from uuid import uuid4

        from tests.test_validation import payload

        assert client.post("/v1/memories", json=payload(request_id=str(uuid4()))).status_code == 201
    body = {"scope": "project", "project_id": "contextbridge"}
    assert client.post("/v1/consolidations", json=body).status_code == 503
    client.app.state.settings = client.app.state.settings.model_copy(
        update={"capture_project_id": "contextbridge"}
    )
    from contextbridge.engine.modules import ModuleGateway

    client.app.state.modules = ModuleGateway(consolidator=Proposals())
    accepted = client.post("/v1/consolidations", json=body)
    assert accepted.status_code == 200 and accepted.json()["source_count"] == 2
    job_id = accepted.json()["job_id"]
    assert client.get(f"/v1/consolidations/{job_id}").json()["status"] == "queued"
    client.app.state.settings = client.app.state.settings.model_copy(
        update={"capture_project_id": "other"}
    )
    assert client.get(f"/v1/consolidations/{job_id}").status_code == 404

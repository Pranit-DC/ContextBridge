from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from contextbridge.models import Memory, MemoryEdge, MemoryVersion
from tests.test_validation import payload

pytestmark = pytest.mark.integration
PATH = "/v1/maintenance/compact"


def save(client, **changes):
    response = client.post("/v1/memories", json=payload(**changes))
    assert response.status_code == 201
    return response.json()


def plan(keep, *duplicates, **changes):
    return {
        "scope": "project",
        "project_id": "contextbridge",
        "keep": {"memory_id": keep["id"], "expected_version": keep["current_version"]},
        "retire": [
            {"memory_id": m["id"], "expected_version": m["current_version"]} for m in duplicates
        ],
        **changes,
    }


def test_preview_confirm_reduces_active_duplicates_preserves_evidence_history_and_restore(client):
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    keep, duplicate = save(client, valid_from=past), save(client, valid_from=past)
    body = plan(keep, duplicate)
    preview = client.post(PATH, json=body)
    assert preview.status_code == 200 and not preview.json()["applied"]
    assert preview.json()["affected_memory_ids"] == [duplicate["id"]]
    assert client.get(f"/v1/memories/{duplicate['id']}/lifecycle").json()["retired_at"] is None
    result = client.post(
        PATH, json=body | {"confirm": True, "plan_revision": preview.json()["plan_revision"]}
    )
    assert result.status_code == 200 and result.json()["applied"]
    query = {"scope": "project", "project_id": "contextbridge", "query": "PostgreSQL"}
    assert [m["id"] for m in client.post("/v1/memories/search", json=query).json()] == [keep["id"]]
    history = client.get(f"/v1/memories/{duplicate['id']}").json()["history"]
    assert history[0]["source"] == duplicate["version"]["source"]
    assert history[0]["content"] == duplicate["version"]["content"]
    assert len(client.post("/v1/memories/search", json=query | {"as_of": past}).json()) == 2
    restored = client.post(
        f"/v1/memories/{duplicate['id']}/restore",
        json={
            "scope": "project",
            "project_id": "contextbridge",
            "expected_version": 1,
            "source_version": 1,
            "source": payload()["source"],
        },
    )
    assert restored.status_code == 200
    assert client.delete(f"/v1/memories/{duplicate['id']}").status_code == 204
    assert client.get(f"/v1/memories/{keep['id']}").status_code == 200


@pytest.mark.parametrize(
    "changes",
    [
        {"content": "Use SQLite."},
        {"conditions": {"environment": "prod"}},
        {"type": "FACT"},
        {"project_id": "another-project"},
    ],
)
def test_incompatible_batch_is_rejected_without_partial_retirement(client, changes):
    keep, duplicate, different = save(client), save(client), save(client, **changes)
    result = client.post(PATH, json=plan(keep, duplicate, different, confirm=True))
    assert result.status_code in {404, 409}
    assert client.get(f"/v1/memories/{duplicate['id']}/lifecycle").json()["retired_at"] is None


def test_scope_auth_distinct_ids_and_confirmation_revision_are_enforced(client, clients):
    keep, duplicate = save(client), save(client)
    body = plan(keep, duplicate)
    assert clients("foreign").post(PATH, json=body).status_code == 404
    assert client.post(PATH, json=plan(keep, keep)).status_code == 422
    assert client.post(PATH, json=body | {"confirm": True}).status_code == 409
    preview = client.post(PATH, json=body).json()
    correction = {"expected_version": 1, "content": "Use SQLite.", "source": payload()["source"]}
    assert client.put(f"/v1/memories/{duplicate['id']}", json=correction).status_code == 200
    assert (
        client.post(
            PATH, json=body | {"confirm": True, "plan_revision": preview["plan_revision"]}
        ).status_code
        == 409
    )
    assert client.get(f"/v1/memories/{keep['id']}/lifecycle").json()["retired_at"] is None


def test_summary_closure_is_previewed_fenced_and_retired_atomically(client, database):
    keep, duplicate = save(client), save(client)
    summary = save(client, type="STATE", content="Database summary.")
    with Session(database[1]) as db:
        db.add(
            MemoryEdge(
                id=uuid4(),
                relation="derived_from",
                from_version_id=UUID(summary["version"]["id"]),
                to_version_id=UUID(duplicate["version"]["id"]),
            )
        )
        db.commit()
    body = plan(keep, duplicate)
    preview = client.post(PATH, json=body).json()
    assert set(preview["affected_memory_ids"]) == {duplicate["id"], summary["id"]}
    with Session(database[1]) as db:
        version = db.scalar(
            select(MemoryVersion).where(MemoryVersion.memory_id == UUID(summary["id"]))
        )
        version.content = "Changed summary after preview."
        db.commit()
    assert (
        client.post(
            PATH, json=body | {"confirm": True, "plan_revision": preview["plan_revision"]}
        ).status_code
        == 409
    )
    preview = client.post(PATH, json=body).json()
    assert (
        client.post(
            PATH, json=body | {"confirm": True, "plan_revision": preview["plan_revision"]}
        ).status_code
        == 200
    )
    with Session(database[1]) as db:
        assert db.get(Memory, UUID(keep["id"])).retired_at is None
        assert db.get(Memory, UUID(duplicate["id"])).retired_at is not None
        assert db.get(Memory, UUID(summary["id"])).retired_at is not None
    assert client.delete(f"/v1/memories/{duplicate['id']}").status_code == 204
    assert client.get(f"/v1/memories/{summary['id']}").status_code == 404


@pytest.mark.parametrize("defect", ["conflict", "derived", "contested", "claim_key", "event"])
def test_uncertain_derived_or_distinct_claims_are_never_compacted(client, database, defect):
    keep, duplicate = save(client), save(client)
    with Session(database[1]) as db:
        if defect in {"conflict", "derived"}:
            db.add(
                MemoryEdge(
                    id=uuid4(),
                    relation="contradicts" if defect == "conflict" else "derived_from",
                    from_version_id=UUID(keep["version"]["id"]),
                    to_version_id=UUID(duplicate["version"]["id"]),
                )
            )
        elif defect == "contested":
            db.get(MemoryVersion, UUID(duplicate["version"]["id"])).decision_state = "contested"
        else:
            memory = db.get(Memory, UUID(duplicate["id"]))
            if defect == "claim_key":
                memory.claim_key = "different-property"
            else:
                memory.type = "EVENT"
        db.commit()
    assert client.post(PATH, json=plan(keep, duplicate)).status_code == 409


def test_late_cleanup_failure_rolls_back_the_entire_operation(client, monkeypatch):
    from contextbridge.engine import compaction
    from contextbridge.service import MemoryServiceError

    keep, duplicate = save(client), save(client)
    body = plan(keep, duplicate)
    revision = client.post(PATH, json=body).json()["plan_revision"]
    original = compaction.retire_set

    def failing_cleanup(*args):
        original(*args)
        raise MemoryServiceError(503, "Cleanup temporarily unavailable")

    monkeypatch.setattr(compaction, "retire_set", failing_cleanup)
    result = client.post(PATH, json=body | {"confirm": True, "plan_revision": revision})
    assert result.status_code == 503
    assert client.get(f"/v1/memories/{duplicate['id']}/lifecycle").json()["retired_at"] is None
    assert client.get(f"/v1/memories/{duplicate['id']}").json()["history"][0]["valid_to"] is None


def test_foreground_operations_finish_while_consolidation_provider_is_waiting(client, database):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from time import monotonic

    from tests.background.test_consolidation import Proposals, process, setup

    harness, _, job = setup(database)
    entered, release = Event(), Event()

    class WaitingProvider(Proposals):
        def propose(self, records):
            entered.set()
            assert release.wait(10), "Foreground operations blocked behind provider work"
            return super().propose(records)

    with ThreadPoolExecutor(max_workers=1) as executor:
        task = executor.submit(process, database, harness, job, WaitingProvider())
        try:
            assert entered.wait(3)
            started = monotonic()
            keep, duplicate = save(client), save(client)
            body = plan(keep, duplicate)
            revision = client.post(PATH, json=body).json()["plan_revision"]
            result = client.post(PATH, json=body | {"confirm": True, "plan_revision": revision})
            assert result.status_code == 200
            assert client.get("/v1/status").status_code == 200
            assert monotonic() - started < 5
        finally:
            release.set()
        assert task.result(timeout=5)["status"] == "succeeded"

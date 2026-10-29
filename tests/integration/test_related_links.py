"""Automatic real-store relationships, not simulated semantic judgments."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from contextbridge.engine.related import MAX_LINKS
from contextbridge.models import Memory, MemoryEdge, MemoryVersion
from contextbridge.persistence.related import backfill, degree, link_related
from contextbridge.retrieval import RetrievalConfig, Retriever
from contextbridge.schemas import CreateMemory, UpdateMemory
from contextbridge.service import MemoryService
from tests.integration.retrieval_fakes import query
from tests.integration.test_lifecycle import restore_body, retirement
from tests.integration.test_retrieval_api import api
from tests.integration.write_fakes import Harness
from tests.test_validation import payload

pytestmark = pytest.mark.integration
REF = "`db/schema.sql`"


def value(content, **changes):
    body = payload(content=content, type="FACT", **changes)
    body["source"]["evidence"] = content
    return CreateMemory.model_validate(body)


def save(database, content, *, owner="developer-a", **changes):
    with Session(database[1], expire_on_commit=False) as session:
        return MemoryService(session, owner).create(value(content, **changes))


def edges(database):
    with Session(database[1]) as session:
        return list(session.scalars(select(MemoryEdge).where(MemoryEdge.relation == "related_to")))


def test_http_create_inspect_retrieve_and_forget_related_neighbor(database):
    with api(database, Retriever(RetrievalConfig(expand_graph=True))) as client:
        first = client.post(
            "/v1/memories", json=value(f"Migrationanchor uses {REF}.").model_dump(mode="json")
        )
        second = client.post(
            "/v1/memories", json=value(f"Review {REF} before deployment.").model_dump(mode="json")
        )
        assert first.status_code == second.status_code == 201
        left, right = first.json(), second.json()
        detail = client.get(f"/v1/memories/{left['id']}").json()
        assert [edge["relation"] for edge in detail["edges"]] == ["related_to"]
        result = client.post("/v1/retrieval/search", json=query(query="Migrationanchor")).json()
        assert {card["memory_id"] for card in result["cards"]} == {left["id"], right["id"]}
        assert "RELATED_MEMORIES_INCLUDED" in result["warnings"]
        limited = client.post(
            "/v1/retrieval/search", json=query(query="Migrationanchor", limit=1)
        ).json()
        assert [card["memory_id"] for card in limited["cards"]] == [left["id"]]
        assert "RELATED_MEMORIES_INCLUDED" not in limited["warnings"]
        assert client.delete(f"/v1/memories/{right['id']}").status_code == 204
        result = client.post("/v1/retrieval/search", json=query(query="Migrationanchor")).json()
        assert [card["memory_id"] for card in result["cards"]] == [left["id"]]
        assert edges(database) == []
        assert (
            client.get(f"/v1/memories/{left['id']}").json()["history"][0]["source"]["evidence"]
            == left["version"]["content"]
        )


@pytest.mark.parametrize(
    "difference", ["owner", "project", "scope", "conditions", "retired", "contested", "closed"]
)
def test_ineligible_neighbors_cannot_form_edges(database, difference):
    changes = {
        "owner": {"owner": "other-owner"},
        "project": {"project_id": "other-project"},
        "scope": {"scope": "developer", "project_id": None},
        "conditions": {"conditions": {"environment": "production"}},
    }.get(difference, {})
    old = save(database, f"Old reference {REF}.", **changes)
    with Session(database[1]) as session:
        version = session.get(MemoryVersion, old.version.id)
        if difference == "retired":
            session.get(Memory, old.id).retired_at = datetime.now(UTC)
        elif difference == "contested":
            version.decision_state = "contested"
        elif difference == "closed":
            version.status, version.valid_to = "SUPERSEDED", datetime.now(UTC)
        session.commit()
    save(database, f"New reference {REF}.")
    assert edges(database) == []


def test_shared_words_or_unevidenced_identifiers_do_not_create_links(database):
    save(database, f"Supported {REF}.")
    with Session(database[1]) as session:
        body = value(f"An unevidenced reference {REF}.")
        body.source.evidence = "Only a general database discussion."
        MemoryService(session, "developer-a").create(body)
    save(database, "General database discussion.")
    save(database, "Another database discussion.")
    assert edges(database) == []


def test_import_replay_and_concurrent_backfill_are_idempotent(database):
    peer = save(database, f"Deployment reads {REF}.")
    harness = Harness(database)
    job, _, _ = harness.enqueue(f"Migration uses {REF}.")
    result = harness.process(job)
    assert result.status == "succeeded"
    assert harness.process(job).memory_ids == result.memory_ids
    assert len(edges(database)) == 1

    def repeat(_):
        with Session(database[1]) as session:
            return backfill(session, "developer-a", scope="project", project_id="contextbridge")

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert all(r["links_created"] == 0 for r in pool.map(repeat, range(2)))
    assert len(edges(database)) == 1
    assert peer.version.id in {edges(database)[0].from_version_id, edges(database)[0].to_version_id}


def test_new_versions_recompute_links_and_old_edges_remain_historical(database):
    peer = save(database, f"Deployment reads {REF}.")
    target = save(database, f"Migration uses {REF}.")
    with Session(database[1], expire_on_commit=False) as session:
        service = MemoryService(session, "developer-a")
        updated = service.update(
            target.id,
            UpdateMemory(
                expected_version=1,
                content="Use `other/schema.sql` instead.",
                source=value("Use `other/schema.sql` instead.").source,
            ),
        )
        assert len(edges(database)) == 1
        from contextbridge.persistence.repository import PostgresRepository

        assert (
            PostgresRepository(session, "developer-a").expand([str(peer.version.id)], query(), 5)
            == []
        )
        restored = service.update(
            target.id,
            UpdateMemory(
                expected_version=2,
                content=f"Return to {REF}.",
                source=value(f"Return to {REF}.").source,
            ),
        )
        assert restored.version.id != updated.version.id
    assert len(edges(database)) == 2


def test_retire_restore_reevaluates_evidence_and_links(database):
    peer = save(database, f"Deployment reads {REF}.")
    target = save(database, f"Migration uses {REF}.")
    with api(database) as client:
        assert client.post(f"/v1/memories/{target.id}/retire", json=retirement()).status_code == 200
        body = restore_body()
        body["source"]["evidence"] = f"Restore migration using {REF}."
        response = client.post(f"/v1/memories/{target.id}/restore", json=body)
        assert response.status_code == 200
        restored = UUID(response.json()["memory"]["version"]["id"])
    assert any(
        {edge.from_version_id, edge.to_version_id} == {peer.version.id, restored}
        for edge in edges(database)
    )


def test_backfill_existing_memories_paginates_and_rollback_is_atomic(database):
    first = save(database, f"First uses {REF}.")
    second = save(database, f"Second uses {REF}.")
    with Session(database[1]) as session:
        session.query(MemoryEdge).delete()
        session.commit()
        assert link_related(session, "developer-a", first.version.id) == 1
        session.rollback()
        assert edges(database) == []
        cursor, processed = None, 0
        while True:
            page = backfill(
                session,
                "developer-a",
                scope="project",
                project_id="contextbridge",
                after=cursor,
                limit=1,
            )
            processed += page["processed"]
            if page["next_cursor"] is None:
                break
            cursor = UUID(page["next_cursor"])
        assert processed == 2
        assert len(edges(database)) == 1
        assert session.get(MemoryVersion, second.version.id).content == second.version.content


def test_degree_bounds_and_concurrent_creates(database):
    def create(index):
        return save(database, f"Reference {index} uses {REF}.")

    with ThreadPoolExecutor(max_workers=3) as pool:
        saved = list(pool.map(create, range(MAX_LINKS + 3)))
    assert edges(database)
    with Session(database[1]) as session:
        assert all(degree(session, m.version.id) <= MAX_LINKS for m in saved)
        pairs = [(edge.from_version_id, edge.to_version_id) for edge in edges(database)]
        assert len(set(pairs)) == len(pairs)
        assert all(left < right for left, right in pairs)


def test_link_failure_rolls_back_the_memory_write(database, monkeypatch):
    def fail(*args):
        raise RuntimeError("injected link failure")

    monkeypatch.setattr("contextbridge.persistence.related.link_related", fail)
    with pytest.raises(RuntimeError):
        save(database, f"Atomic {REF}.", request_id=str(uuid4()))
    with Session(database[1]) as session:
        assert session.scalar(select(func.count()).select_from(Memory)) == 0


def test_cli_backfills_only_selected_project_and_prints_id_only_progress(
    database, monkeypatch, capsys
):
    import json

    from contextbridge.config import Settings
    from contextbridge.engine import related_cli
    from tests.conftest import TEST_TOKEN

    save(database, f"First uses {REF}.")
    save(database, f"Second uses {REF}.")
    save(database, f"Other project uses {REF}.", project_id="other-project")
    with Session(database[1]) as session:
        session.query(MemoryEdge).delete()
        session.commit()
    settings = Settings(
        _env_file=None, database_url=database[0], api_token=TEST_TOKEN, developer_id="developer-a"
    )
    monkeypatch.setattr(related_cli, "Settings", lambda: settings)
    assert related_cli.main(["--project-id", "contextbridge"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result == {"processed": 2, "links_created": 1, "next_cursor": None}
    assert len(edges(database)) == 1


def test_specific_edges_suppress_generic_links_and_developer_opt_in_is_isolated(database):
    first = save(database, f"First uses {REF}.", scope="developer", project_id=None)
    second = save(database, f"Second uses {REF}.", scope="developer", project_id=None)
    with Session(database[1]) as session:
        session.query(MemoryEdge).delete()
        session.add(
            MemoryEdge(
                id=uuid4(),
                from_version_id=first.version.id,
                to_version_id=second.version.id,
                relation="derived_from",
            )
        )
        session.commit()
        result = backfill(session, "developer-a", scope="project", project_id="contextbridge")
        assert result["processed"] == 0
        result = backfill(session, "developer-a", scope="developer", project_id=None)
        assert result["processed"] == 2 and result["links_created"] == 0
        assert edges(database) == []

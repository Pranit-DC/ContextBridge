import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from contextbridge.engine.errors import EngineError
from contextbridge.models import MemoryEdge, MemoryEmbedding
from contextbridge.persistence.repository import PostgresRepository
from contextbridge.persistence.vectors import vector_available
from contextbridge.schemas import UpdateMemory
from contextbridge.service import MemoryService
from tests.integration.retrieval_fakes import create, embedding, index, query

pytestmark = pytest.mark.integration


@pytest.fixture
def vector_database(database):
    with Session(database[1]) as session:
        available = vector_available(session)
    if not available:
        if os.getenv("CONTEXTBRIDGE_REQUIRE_VECTOR") == "1":
            pytest.fail("The vector integration job requires an installed pgvector extension")
        pytest.skip("Core-only PostgreSQL: real vector assertions run in pgvector 17/18 CI jobs")
    return database


@pytest.mark.parametrize("channel", ["lexical", "symbolic"])
def test_channel_scope_conditions_and_time_apply_before_limit(database, channel):
    create(database, project_id="other-project")
    create(database, owner="other-owner")
    create(database, conditions={"environment": "production"})
    global_memory = create(database, scope="developer", project_id=None)
    target = create(database)
    with Session(database[1]) as session:
        repository = PostgresRepository(session, "developer-a")
        matches = repository.search_channel(channel, query(), None, 1)
        assert [match["record"]["memory"]["id"] for match in matches] == [str(target.id)]
        included = repository.search_channel(channel, query(include_developer=True), None, 200)
        assert {match["record"]["memory"]["id"] for match in included} == {
            str(target.id),
            str(global_memory.id),
        }
        historical = query(as_of=(datetime.now(UTC) - timedelta(days=1)).isoformat())
        assert repository.search_channel(channel, historical, None, 1) == []


def test_symbolic_preserves_identifiers_and_literal_wildcards(database):
    target = create(database, content="DATABASE_URL is app.db-v2.")
    create(database, content="DATABASEXURL is app.db-v3.")
    with Session(database[1]) as session:
        matches = PostgresRepository(session, "developer-a").search_channel(
            "symbolic", query(query="DATABASE_URL"), None, 200
        )
    assert [match["record"]["memory"]["id"] for match in matches] == [str(target.id)]


def test_real_vector_distance_filters_before_limit(vector_database):
    database = vector_database
    foreign = create(database, project_id="other-project")
    conditional = create(database, conditions={"environment": "production"})
    other_owner = create(database, owner="other-owner")
    global_memory = create(database, scope="developer", project_id=None)
    target = create(database)
    index(database, [foreign], [[1, 0]], project_id="other-project")
    index(database, [conditional], [[1, 0]], conditions={"environment": "production"})
    index(database, [other_owner], [[1, 0]], owner="other-owner")
    index(database, [global_memory], [[1, 0]], scope="developer", project_id=None)
    index(database, [target], [[0.8, 0.6]])
    with Session(database[1]) as session:
        repository = PostgresRepository(session, "developer-a")
        matches = repository.search_channel("semantic", query(), embedding(), 1)
        assert matches[0]["record"]["memory"]["id"] == str(target.id)
        assert matches[0]["channel"] == "semantic" and matches[0]["rank"] == 1
        included = repository.search_channel(
            "semantic", query(include_developer=True), embedding(), 1
        )
        assert included[0]["record"]["memory"]["id"] == str(global_memory.id)
        assert repository.warnings == set()


def test_model_compatibility_missing_and_stale_embeddings(vector_database):
    database = vector_database
    target = create(database)
    index(database, [target], [[1, 0]])
    index(database, [target], [[0, 1]], model_id="other-model")
    with Session(database[1]) as session:
        repository = PostgresRepository(session, "developer-a")
        assert repository.search_channel("semantic", query(), embedding(), 20)
        with pytest.raises(EngineError, match="INVALID_INPUT"):
            repository.search_channel(
                "semantic", query(), embedding(dimensions=3, vector=[1, 0, 0]), 20
            )
        session.rollback()
        assert (
            repository.search_channel("semantic", query(), embedding(model_id="missing-model"), 20)
            == []
        )
        assert repository.warnings == {"EMBEDDING_UNAVAILABLE"}
        session.execute(
            text(
                "UPDATE memory_embeddings SET content_fingerprint=:fingerprint "
                "WHERE model_id=:model"
            ),
            {"fingerprint": "0" * 64, "model": "recorded-v1"},
        )
        session.commit()
        assert repository.search_channel("semantic", query(), embedding(), 20) == []
        assert session.scalar(select(func.count()).select_from(MemoryEmbedding)) == 2


def test_historical_vectors_and_liveness_use_effective_intervals(vector_database):
    database = vector_database
    start = datetime.now(UTC) - timedelta(days=3)
    change = start + timedelta(days=1)
    target = create(database, valid_from=start.isoformat())
    index(database, [target], [[1, 0]])
    with Session(database[1], expire_on_commit=False) as session:
        updated = MemoryService(session, "developer-a").update(
            target.id,
            UpdateMemory(
                expected_version=1,
                content="Use SQLite database.",
                source=target.version.source,
                valid_from=change,
            ),
        )
    index(database, [updated], [[0, 1]])
    with Session(database[1]) as session:
        repository = PostgresRepository(session, "developer-a")
        old_query = query(as_of=(start + timedelta(hours=1)).isoformat())
        assert repository.is_live(str(target.version.id), old_query)
        assert not repository.is_live(str(target.version.id), query())
        matches = repository.search_channel("semantic", old_query, embedding(), 20)
        assert [match["record"]["memory"]["version"]["number"] for match in matches] == [1]
        matches = repository.search_channel("semantic", query(), embedding(vector=[0, 1]), 20)
        assert [match["record"]["memory"]["version"]["number"] for match in matches] == [2]
        inspected = repository.inspect(str(target.id), old_query)
        assert [version["number"] for version in inspected["history"]] == [1]
        MemoryService(session, "developer-a").forget(target.id)
        assert not repository.is_live(str(updated.version.id), query())


def test_graph_expansion_filters_every_hop_and_bounds_depth(database):
    records = [create(database, content=f"Database decision {i}.") for i in range(4)]
    foreign = create(database, project_id="other-project")
    conditional = create(database, conditions={"environment": "production"})
    with Session(database[1]) as session:
        for left, right in [
            (records[0], records[1]),
            (records[1], records[2]),
            (records[2], records[3]),
            (records[0], foreign),
            (records[0], conditional),
        ]:
            session.add(
                MemoryEdge(
                    id=uuid4(),
                    from_version_id=left.version.id,
                    to_version_id=right.version.id,
                    relation="related_to",
                )
            )
        session.commit()
        repository = PostgresRepository(session, "developer-a")
        expanded = repository.expand([str(records[0].version.id)], query(), 200)
        assert {record["memory"]["id"] for record in expanded} == {
            str(records[1].id),
            str(records[2].id),
        }
        assert len(repository.expand([str(records[0].version.id)], query(), 1)) == 1
        with pytest.raises(EngineError, match="OUT_OF_SCOPE"):
            repository.expand([str(foreign.version.id)], query(), 200)
        session.rollback()
        inspected = repository.inspect(str(records[0].id), query())
        assert len(inspected["edges"]) == 1
        with pytest.raises(EngineError, match="OUT_OF_SCOPE"):
            repository.inspect(str(foreign.id), query())


def test_missing_extension_degrades_without_breaking_lexical_search(database, monkeypatch):
    import contextbridge.persistence.repository as repository_module

    target = create(database)
    monkeypatch.setattr(repository_module, "vector_available", lambda session: False)
    with Session(database[1]) as session:
        repository = PostgresRepository(session, "developer-a")
        assert repository.search_channel("semantic", query(), embedding(), 1) == []
        assert repository.warnings == {"EMBEDDING_UNAVAILABLE"}
        assert repository.search_channel("lexical", query(), None, 1)[0]["record"]["memory"][
            "id"
        ] == str(target.id)


@pytest.mark.parametrize("channel,limit", [("unknown", 20), ("lexical", 201), ("lexical", True)])
def test_repository_rejects_invalid_channel_bounds(database, channel, limit):
    with Session(database[1]) as session:
        with pytest.raises(EngineError, match="INVALID_INPUT"):
            PostgresRepository(session, "developer-a").search_channel(channel, query(), None, limit)


def test_semantic_search_abstains_in_small_store_and_keeps_relevant_matches(vector_database):
    target = create(vector_database, content="The project uses PostgreSQL.")
    index(vector_database, [target], [[1, 0]])
    with Session(vector_database[1]) as session:
        repository = PostgresRepository(session, "developer-a")
        unrelated = repository.search_channel(
            "semantic", query(query="unrelated question"), embedding(vector=[0.08, 0.997]), 3
        )
        assert unrelated == []
        relevant = repository.search_channel(
            "semantic", query(query="chosen datastore"), embedding(vector=[0.8, 0.6]), 3
        )
        assert [r["record"]["memory"]["id"] for r in relevant] == [str(target.id)]
        assert repository.warnings == set()

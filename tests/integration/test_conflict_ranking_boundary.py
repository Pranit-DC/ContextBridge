from uuid import uuid4

from sqlalchemy.orm import Session

from contextbridge.models import MemoryEdge, MemoryVersion
from tests.integration.retrieval_fakes import RecordedRetriever, create, query
from tests.integration.test_retrieval_api import api


def test_real_conflict_edges_preserve_uncertainty_and_explicit_limits(database):
    first = create(database, content="Database SQLite.")
    second = create(database, content="Database PostgreSQL.")
    with Session(database[1]) as db:
        for memory in (first, second):
            db.get(MemoryVersion, memory.version.id).decision_state = "contested"
        db.add(
            MemoryEdge(
                id=uuid4(),
                from_version_id=first.version.id,
                to_version_id=second.version.id,
                relation="contradicts",
            )
        )
        db.commit()
    with api(database, RecordedRetriever()) as client:
        result = client.post("/v1/retrieval/search", json=query(limit=2)).json()
        assert {card["memory_id"] for card in result["cards"]} == {str(first.id), str(second.id)}
        assert all(card["verification"] == "uncertain" for card in result["cards"])
        limited = client.post("/v1/retrieval/search", json=query(limit=1)).json()
        assert len(limited["cards"]) == 1
        assert "CONFLICT_ALTERNATIVES_OMITTED" in limited["warnings"]


def test_ranking_does_not_expose_edges_in_other_projects_or_conditions(database):
    first = create(database)
    other = create(database, project_id="private-project")
    conditional = create(database, conditions={"environment": "production"})
    with Session(database[1]) as db:
        for memory in (other, conditional):
            db.add(
                MemoryEdge(
                    id=uuid4(),
                    from_version_id=first.version.id,
                    to_version_id=memory.version.id,
                    relation="contradicts",
                )
            )
        db.commit()
    with api(database, RecordedRetriever()) as client:
        result = client.post("/v1/retrieval/search", json=query()).json()
        assert [card["memory_id"] for card in result["cards"]] == [str(first.id)]
        assert not any("CONFLICT" in warning for warning in result["warnings"])

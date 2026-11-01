from uuid import uuid4

from sqlalchemy.orm import Session

from contextbridge.models import MemoryEdge, MemoryVersion
from contextbridge.retrieval.retriever import RetrievalConfig, Retriever
from tests.integration.retrieval_fakes import RecordedRetriever, create, query
from tests.integration.test_retrieval_api import api


def test_expansion_cannot_displace_direct_contested_match_at_requested_limit(database):
    direct = create(database, content="SQLite database.")
    related = create(database, content="Python runtime.")
    with Session(database[1]) as db:
        db.get(MemoryVersion, direct.version.id).decision_state = "contested"
        db.add(
            MemoryEdge(
                id=uuid4(),
                from_version_id=direct.version.id,
                to_version_id=related.version.id,
                relation="related_to",
            )
        )
        db.commit()
    with api(database, Retriever(RetrievalConfig(expand_graph=True))) as client:
        limited = client.post("/v1/retrieval/search", json=query(limit=1))
        assert limited.status_code == 200
        assert [card["memory_id"] for card in limited.json()["cards"]] == [str(direct.id)]
        assert "RELATED_MEMORIES_INCLUDED" not in limited.json()["warnings"]
        expanded = client.post("/v1/retrieval/search", json=query(limit=2))
        assert expanded.status_code == 200
        assert [card["memory_id"] for card in expanded.json()["cards"]] == [
            str(direct.id),
            str(related.id),
        ]


def test_valid_warning_capacity_does_not_turn_conflicted_results_into_503(database):
    memory = create(database)
    with Session(database[1]) as db:
        db.get(MemoryVersion, memory.version.id).decision_state = "contested"
        db.commit()

    class NoisyRetriever(RecordedRetriever):
        def search(self, *args):
            result = super().search(*args)
            result["warnings"] = [f"SYNTHETIC_WARNING_{i}" for i in range(20)]
            return result

    with api(database, NoisyRetriever()) as client:
        response = client.post("/v1/retrieval/search", json=query())
        assert response.status_code == 200
        assert len(response.json()["warnings"]) <= 20
        assert "WARNINGS_OMITTED" in response.json()["warnings"]
        assert "UNRESOLVED_CONFLICT_CONTEXT" in response.json()["warnings"]


def test_project_topic_noun_is_not_mistaken_for_another_project_binding(database):
    memory = create(database, content="Project database SQLite.")
    with api(database, RecordedRetriever()) as client:
        response = client.post("/v1/retrieval/search", json=query(query="project database"))
        assert response.status_code == 200
        assert [card["memory_id"] for card in response.json()["cards"]] == [str(memory.id)]


def test_clarification_does_not_bypass_existing_secret_rejection(database):
    with api(database, RecordedRetriever()) as client:
        response = client.post(
            "/v1/retrieval/search",
            json=query(query="What DB for V1?", conditions={"password": "private-rejected-value"}),
        )
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "INVALID_INPUT"
        assert "private-rejected-value" not in response.text

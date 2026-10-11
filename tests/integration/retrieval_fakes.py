"""Recorded test substitutes, independent of Harshal's ranking/model modules."""

from uuid import uuid4

from sqlalchemy.orm import Session

from contextbridge.contracts import MemoryCard
from contextbridge.engine.indexing import IndexService
from contextbridge.schemas import CreateMemory
from contextbridge.service import MemoryService
from tests.test_validation import payload


def query(**changes):
    return {
        "schema_version": 1,
        "scope": "project",
        "project_id": "contextbridge",
        "query": "database",
        **changes,
    }


def create(database, content="Use PostgreSQL database.", owner="developer-a", **changes):
    with Session(database[1], expire_on_commit=False) as session:
        return MemoryService(session, owner).create(
            CreateMemory.model_validate(
                payload(request_id=str(uuid4()), content=content, **changes)
            )
        )


class RecordedEmbedder:
    def __init__(self, vectors, model_id="recorded-v1", dimensions=2):
        self.vectors, self.model_id, self.dimensions = vectors, model_id, dimensions
        self.calls = []

    def embed(self, texts):
        self.calls.append(texts)
        return {"model_id": self.model_id, "dimensions": self.dimensions, "vectors": self.vectors}


def index(database, memories, vectors, owner="developer-a", model_id="recorded-v1", **filters):
    provider = RecordedEmbedder(vectors, model_id)
    with Session(database[1], expire_on_commit=False) as session:
        service = IndexService(session, owner)
        job_id = service.enqueue(
            query(**filters), [str(m.version.id) for m in memories], model_id, 2, str(uuid4())
        )
        assert service.process(job_id, provider)["status"] == "succeeded"
    return job_id


def embedding(**changes):
    return {"model_id": "recorded-v1", "dimensions": 2, "vector": [1.0, 0.0], **changes}


def card(record):
    memory = record["memory"]
    version = memory["version"]
    return MemoryCard(
        memory_id=memory["id"],
        version_id=version["id"],
        version_number=version["number"],
        type=memory["type"],
        content=version["content"],
        scope=memory["scope"],
        project_id=memory["project_id"],
        conditions=memory["conditions"],
        valid_from=version["valid_from"],
        valid_to=version["valid_to"],
        decision_state=record["decision_state"],
        verification="not_requested",
        source_ref={key: version["source"][key] for key in ["agent", "session", "interaction"]},
    ).model_dump(mode="json")


class RecordedRetriever:
    def search(self, query, repository, embedder, verifier):
        matches = repository.search_channel("lexical", query, None, query["limit"])
        repository.search_channel("semantic", query, embedding(), query["limit"])
        return {
            "schema_version": 1,
            "cards": [card(match["record"]) for match in matches],
            "degraded": False,
            "warnings": [],
        }

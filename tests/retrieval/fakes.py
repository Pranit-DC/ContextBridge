"""Test substitutes. They prove policy behavior only, not real SQL, vectors, or model quality."""

import copy
import json
from pathlib import Path
from uuid import uuid4

FIXTURES = Path(__file__).resolve().parents[2] / "docs" / "team-plan" / "fixtures"


def snapshot() -> dict:
    return json.loads((FIXTURES / "retrieval-snapshot.json").read_text(encoding="utf-8"))


def make_record(
    content="A fact.",
    *,
    scope="project",
    project_id="contextbridge",
    conditions=None,
    status="ACTIVE",
    valid_from="2026-10-09T10:00:00Z",
    valid_to=None,
    decision_state="clear",
    created_at="2026-10-09T10:00:01Z",
    memory_id=None,
    number=1,
) -> dict:
    record = copy.deepcopy(snapshot()["records"][0])
    memory = record["memory"]
    memory.update(
        id=memory_id or str(uuid4()),
        scope=scope,
        project_id=project_id if scope == "project" else None,
        conditions=conditions or {},
        created_at=created_at,
        current_version=number,
    )
    memory["version"].update(
        id=str(uuid4()),
        number=number,
        content=content,
        status=status,
        valid_from=valid_from,
        valid_to=valid_to,
    )
    record["decision_state"] = decision_state
    return record


def version_id(record: dict) -> str:
    return record["memory"]["version"]["id"]


def match(record: dict, channel: str, rank: int) -> dict:
    return {"record": record, "channel": channel, "rank": rank}


def query(**overrides) -> dict:
    base = copy.deepcopy(snapshot()["query"])
    base.update(overrides)
    return base


class FakeRepository:
    """Returns exactly what it is given, with no filtering, so tests can inject bad records."""

    def __init__(self, **channels):
        self.channels = {"lexical": [], "semantic": [], "symbolic": [], **channels}
        self.live: set[str] | None = None  # None: everything is live
        self.failing: dict[str, Exception] = {}
        self.calls: list[tuple] = []
        self.liveness_calls: list[str] = []

    def search_channel(self, channel, query, query_embedding, limit):
        self.calls.append((channel, query, query_embedding, limit))
        if channel in self.failing:
            raise self.failing[channel]
        return self.channels[channel]

    def expand(self, version_ids, query, limit):
        raise AssertionError("Graph expansion belongs to a later phase")

    def inspect(self, memory_id, query):
        raise AssertionError("Verification belongs to a later phase")

    def is_live(self, version_id, query):
        self.liveness_calls.append(version_id)
        if "liveness" in self.failing:
            raise self.failing["liveness"]
        return self.live is None or version_id in self.live


class FakeEmbedder:
    def __init__(self, vectors=None, model_id="fake-embed", dimensions=2, error=None):
        self.batch = {
            "model_id": model_id,
            "dimensions": dimensions,
            "vectors": vectors if vectors is not None else [[0.1, 0.2]],
        }
        self.error = error
        self.texts: list[list[str]] = []

    def embed(self, texts):
        self.texts.append(texts)
        if self.error:
            raise self.error
        return self.batch


class FakeVerifier:
    def verify(self, record, inspection):
        raise AssertionError("Verification belongs to a later phase")


def inspection_for(record: dict, *, history=None) -> dict:
    """What an authorized inspection of this record's memory would return."""
    memory = copy.deepcopy(record["memory"])
    return {
        "memory": memory,
        "history": history if history is not None else [copy.deepcopy(memory["version"])],
        "edges": [],
    }


class FakeJudge:
    def __init__(self, outcome="supports", error=None):
        self.outcome, self.error = outcome, error
        self.calls: list[tuple[str, str]] = []

    def judge(self, claim, evidence):
        self.calls.append((claim, evidence))
        if self.error:
            raise self.error
        return self.outcome

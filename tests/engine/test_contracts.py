from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from contextbridge.contracts import (
    AdmissionDecision,
    BrowseQuery,
    Candidate,
    CapturedEvent,
    EmbeddingBatch,
    MemoryRecord,
    QueryEmbedding,
    RetrievalQuery,
    RetrievalResult,
    WritePlan,
)
from tests.engine.fakes import fixture


@pytest.mark.parametrize(
    ("model", "name"),
    [
        (CapturedEvent, "captured-event"),
        (Candidate, "candidate"),
        (AdmissionDecision, "admission-decision"),
        (RetrievalResult, "retrieval-result"),
    ],
)
def test_agreed_fixture_round_trip(model, name):
    value = fixture(name)
    assert model.model_validate(value).model_dump(mode="json") == value


def test_retrieval_snapshot_preserves_nested_memory_and_explicit_null_confidence():
    snapshot = fixture("retrieval-snapshot")
    RetrievalQuery.model_validate(snapshot["query"])
    record = snapshot["records"][0]
    record.update(claim_key=None, confidence=None)
    parsed = MemoryRecord.model_validate(record)
    assert parsed.memory.version.source.kind == "user"
    assert parsed.confidence is None


@pytest.mark.parametrize("version", [None, 0, 2, True, "1", 1.0])
def test_contract_version_is_explicit_integer_one(version):
    value = fixture("captured-event")
    value["schema_version"] = version
    with pytest.raises(ValidationError):
        CapturedEvent.model_validate(value)


def test_contract_version_is_required():
    value = fixture("captured-event")
    del value["schema_version"]
    with pytest.raises(ValidationError):
        CapturedEvent.model_validate(value)


@pytest.mark.parametrize(
    "changes",
    [
        {"scope": "project", "project_id": None},
        {"scope": "developer", "project_id": "contextbridge"},
        {"occurred_at": "2026-01-01T00:00:00"},
        {"occurred_at": datetime.now(UTC) + timedelta(days=1)},
        {"developer_id": "other-owner"},
        {"capture_method": "unverified_hook"},
        {"messages": []},
    ],
)
def test_invalid_event_boundary(changes):
    value = fixture("captured-event")
    value.update(changes)
    with pytest.raises(ValidationError):
        CapturedEvent.model_validate(value)


@pytest.mark.parametrize(("count", "size"), [(21, 1), (1, 8001), (5, 6401)])
def test_message_count_and_aggregate_bounds(count, size):
    value = fixture("captured-event")
    value["messages"] = [
        {"message_id": f"message-{i}", "role": "user", "content": "x" * size} for i in range(count)
    ]
    with pytest.raises(ValidationError):
        CapturedEvent.model_validate(value)


def test_duplicate_message_ids_rejected_and_timezone_normalized():
    value = fixture("captured-event")
    value["occurred_at"] = "2026-10-09T15:30:00+05:30"
    assert (
        CapturedEvent.model_validate(value).occurred_at.isoformat() == "2026-10-09T10:00:00+00:00"
    )
    value["messages"].append(deepcopy(value["messages"][0]))
    with pytest.raises(ValidationError):
        CapturedEvent.model_validate(value)


@pytest.mark.parametrize("score", [-0.1, 1.1, float("nan"), float("inf")])
def test_invalid_candidate_scores(score):
    value = fixture("candidate")
    value["confidence"] = score
    with pytest.raises(ValidationError):
        Candidate.model_validate(value)


def test_candidate_references_are_bounded_to_its_event():
    value = fixture("candidate")
    value["evidence_refs"][0]["event_id"] = str(uuid4())
    with pytest.raises(ValidationError):
        Candidate.model_validate(value)


@pytest.mark.parametrize(
    ("operation", "target", "version"),
    [
        ("UPDATE", None, 1),
        ("UPDATE", str(uuid4()), None),
        ("LINK_CONFLICT", None, None),
        ("CREATE", str(uuid4()), None),
        ("CREATE", None, 1),
    ],
)
def test_write_plan_cannot_hide_missing_concurrency_preconditions(operation, target, version):
    with pytest.raises(ValidationError):
        WritePlan(
            schema_version=1,
            candidate_id=uuid4(),
            operation=operation,
            target_memory_id=target,
            expected_version=version,
            reason_codes=[],
        )


@pytest.mark.parametrize("vectors", [[[1.0]], [[1.0, float("nan")]], [[1.0, float("inf")]]])
def test_embedding_shape_and_finite_values(vectors):
    with pytest.raises(ValidationError):
        EmbeddingBatch(model_id="fake-model", dimensions=2, vectors=vectors)
    with pytest.raises(ValidationError):
        QueryEmbedding(model_id="fake-model", dimensions=2, vector=vectors[0])


def test_browse_has_separate_pagination_limit():
    query = BrowseQuery(schema_version=1, scope="project", project_id="contextbridge")
    assert query.limit == 20 and query.cursor is None
    with pytest.raises(ValidationError):
        BrowseQuery(schema_version=1, scope="developer", limit=101)

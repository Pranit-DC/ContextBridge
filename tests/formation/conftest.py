import json
from pathlib import Path

import pytest

from contextbridge.contracts import Candidate, CapturedEvent

FIXTURES = Path(__file__).resolve().parents[2] / "docs" / "team-plan" / "fixtures"


@pytest.fixture
def event():
    raw = json.loads((FIXTURES / "captured-event.json").read_text(encoding="utf-8"))
    return CapturedEvent.model_validate(raw).model_dump(mode="json")


@pytest.fixture
def candidate():
    raw = json.loads((FIXTURES / "candidate.json").read_text(encoding="utf-8"))
    return Candidate.model_validate(raw).model_dump(mode="json")


@pytest.fixture
def context():
    return {"schema_version": 1, "checked_at": "2026-10-09T11:00:00Z", "records": []}


@pytest.fixture
def record():
    raw = json.loads((FIXTURES / "retrieval-snapshot.json").read_text(encoding="utf-8"))
    return raw["records"][0]

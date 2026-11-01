import json

import pytest

from contextbridge.engine.errors import ModuleError
from contextbridge.formation.providers.interpretation import (
    ChatRelationInterpreter,
    ChatSearchEvidenceJudge,
)
from tests.formation.test_groq_provider import settings


class Client:
    settings = settings()

    def __init__(self, response):
        self.response = response
        self.calls = []

    def complete(self, model, prompt, payload, schema):
        self.calls.append(payload)
        return json.dumps(self.response)


@pytest.mark.parametrize(
    "evidence,excerpt,expected",
    [
        ("Use SQLite.", "Use SQLite.", "uncertain"),
        ("Use SQLite instead of PostgreSQL.", "Use SQLite instead of PostgreSQL.", "correction"),
        ("Use SQLite.", "Correct the old value.", "uncertain"),
        ("Use SQLite instead of PostgreSQL.", None, "uncertain"),
    ],
)
def test_new_assertion_is_never_an_explicit_correction(
    candidate, record, evidence, excerpt, expected
):
    candidate["source"]["evidence"] = evidence
    client = Client({"relation": "correction", "correction_evidence": excerpt})
    assert ChatRelationInterpreter(client).compare(candidate, record) == expected


def test_condition_mismatch_never_calls_model(candidate, record):
    record["memory"]["conditions"] = {"environment": "production"}
    client = Client({"relation": "same"})
    assert ChatRelationInterpreter(client).compare(candidate, record) == "unrelated"
    assert client.calls == []


@pytest.mark.parametrize(
    "evidence",
    [
        "Do not change the database to SQLite.",
        "Don't replace PostgreSQL.",
        "Never switch the database to SQLite.",
        "You mustn’t change PostgreSQL.",
    ],
)
def test_negated_instruction_cannot_be_promoted_to_a_correction(candidate, record, evidence):
    candidate["source"]["evidence"] = evidence
    client = Client({"relation": "correction", "correction_evidence": evidence})
    assert ChatRelationInterpreter(client).compare(candidate, record) == "uncertain"


@pytest.mark.parametrize("value", ["latest_wins", None, True])
def test_malformed_relation_cannot_reach_engine(candidate, record, value):
    with pytest.raises(ModuleError, match="INVALID_PROVIDER_OUTPUT"):
        ChatRelationInterpreter(Client({"relation": value})).compare(candidate, record)


def test_evidence_judge_preserves_negation_and_returns_only_valid_judgments():
    client = Client({"judgment": "contradicts"})
    assert (
        ChatSearchEvidenceJudge(client).judge("Use SQLite.", "Do not use SQLite.") == "contradicts"
    )
    assert client.calls == [{"claim": "Use SQLite.", "evidence": "Do not use SQLite."}]

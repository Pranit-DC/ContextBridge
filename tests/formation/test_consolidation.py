"""Synthetic policy tests, separate from actual model quality and database fencing."""

import json
from copy import deepcopy
from uuid import uuid4

import pytest

from contextbridge.contracts import ConsolidationProposal, MemoryRecord
from contextbridge.engine.errors import ModuleError
from contextbridge.formation import Consolidator
from contextbridge.formation.consolidation import MAX_GROUPING_CHARACTERS, MAX_INPUT_CHARACTERS
from contextbridge.formation.providers.consolidation import (
    RecordedConsolidationVerifier,
    RecordedGroupingProvider,
)


def sources(record):
    records = [deepcopy(record), deepcopy(record)]
    second = records[1]
    second["memory"]["id"] = str(uuid4())
    second["memory"]["version"]["id"] = str(uuid4())
    second["memory"]["type"] = "LESSON"
    second["memory"]["version"]["content"] = (
        "Never drop audit.sql; keep its 7-day backup before upgrading."
    )
    second["memory"]["version"]["source"]["evidence"] = second["memory"]["version"]["content"]
    second["memory"]["version"]["source"]["interaction"] = "rare-lesson"
    second["claim_key"] = "database.backup.lesson"
    return [MemoryRecord.model_validate(r).model_dump(mode="json") for r in records]


class Group:
    """Synthetic all-in-one grouping, used only to probe policy failure paths."""

    def __init__(self):
        self.calls = []

    def group(self, records):
        self.calls.append(deepcopy(records))
        return json.dumps({"groups": [[r["memory"]["version"]["id"] for r in records]]})


class Verify:
    def __init__(self, label="supported"):
        self.label, self.calls = label, []

    def verify(self, proposal, records):
        self.calls.append((deepcopy(proposal), deepcopy(records)))
        return self.label


def test_proposal_preserves_rare_negation_units_types_and_all_provenance(record):
    records = sources(record)
    ids = [r["memory"]["version"]["id"] for r in records]
    module = Consolidator(
        RecordedGroupingProvider([(records, [ids])]),
        RecordedConsolidationVerifier([(records, "supported")]),
    )
    proposal = module.propose(records)[0]
    ConsolidationProposal.model_validate(proposal)
    assert set(proposal["source_version_ids"]) == set(ids)
    for r in records:
        assert r["memory"]["version"]["content"] in proposal["summary"]
        source = r["memory"]["version"]["source"]
        assert {key: source[key] for key in ("agent", "session", "interaction")} in proposal[
            "source_refs"
        ]
    assert "[LESSON]" in proposal["summary"]
    assert module.propose(list(reversed(records))) == [proposal]
    changed = deepcopy(records)
    changed[0]["memory"]["version"]["source"]["interaction"] = "unlabelled"
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        module.propose(changed)


@pytest.mark.parametrize("label", ["unsupported", "uncertain"])
def test_unknown_or_unsupported_source_meaning_is_not_proposed(record, label):
    records = sources(record)
    records[1]["memory"]["version"]["content"] = "The user prefers SQLite."
    records[1]["memory"]["version"]["source"]["evidence"] = (
        "An assistant suggested SQLite; the user did not adopt it."
    )
    assert Consolidator(Group(), Verify(label)).propose(records) == []


def test_contested_and_same_key_differences_abstain_without_deciding_truth(record):
    records = sources(record)
    records[1]["claim_key"] = records[0]["claim_key"]
    verifier = Verify()
    assert Consolidator(Group(), verifier).propose(records) == []
    assert verifier.calls == []
    records[1]["claim_key"] = None
    records[0]["decision_state"] = "contested"
    provider = Group()
    assert Consolidator(provider, verifier).propose(records) == []
    assert provider.calls == []


@pytest.mark.parametrize("boundary", ["project", "conditions", "scope"])
def test_partition_before_provider_and_no_cross_boundary_proposal(record, boundary):
    records = sources(record)
    other = deepcopy(records)
    for r in other:
        r["memory"]["id"], r["memory"]["version"]["id"] = str(uuid4()), str(uuid4())
        if boundary == "project":
            r["memory"]["project_id"] = "other-project"
        elif boundary == "conditions":
            r["memory"]["conditions"] = {"env": "production"}
        else:
            r["memory"].update(scope="developer", project_id=None)
    provider = Group()
    proposals = Consolidator(provider, Verify()).propose(records + other)
    assert len(proposals) == len(provider.calls) == 2
    for bucket, proposal in zip(provider.calls, proposals, strict=True):
        first = bucket[0]["memory"]
        assert all(
            (r["memory"]["scope"], r["memory"]["project_id"], r["memory"]["conditions"])
            == (first["scope"], first["project_id"], first["conditions"])
            for r in bucket
        )
        assert proposal["source_version_ids"] == [r["memory"]["version"]["id"] for r in bucket]


@pytest.mark.parametrize(
    "change",
    [
        "version",
        "closed",
        "status",
        "future",
        "recorded_future",
        "created_future",
    ],
)
def test_stale_snapshot_never_calls_provider(record, change):
    records = sources(record)
    memory = records[0]["memory"]
    version = memory["version"]
    if change == "version":
        memory["current_version"] = 2
    elif change == "closed":
        version["valid_to"] = "2026-10-10T11:00:00+00:00"
    elif change == "status":
        version["status"] = "SUPERSEDED"
    elif change == "future":
        version["valid_from"] = "2099-01-01T00:00:00+00:00"
    elif change == "recorded_future":
        version["recorded_at"] = "2099-01-01T00:00:00+00:00"
    else:
        memory["created_at"] = "2099-01-01T00:00:00+00:00"
    provider = Group()
    with pytest.raises(ModuleError, match="VERSION_CONFLICT"):
        Consolidator(provider, Verify()).propose(records)
    assert provider.calls == []


@pytest.mark.parametrize(
    "change",
    [
        "missing_evidence",
        "blank_evidence",
        "assistant",
        "scope",
        "condition_limit",
        "condition_key",
        "content_limit",
        "naive",
        "zero",
        "bool",
        "duplicate_memory",
        "duplicate_version",
        "secret",
        "secret_source",
        "secret_condition",
        "nonfinite",
        "tuple",
        "many",
        "cycle",
        "input_limit",
    ],
)
def test_invalid_or_sensitive_input_is_sanitized_before_provider(record, change):
    records = sources(record)
    memory, version = records[0]["memory"], records[0]["memory"]["version"]
    if change == "missing_evidence":
        del version["source"]["evidence"]
    elif change == "blank_evidence":
        version["source"]["evidence"] = "   "
    elif change == "assistant":
        version["source"]["kind"] = "assistant"
    elif change == "scope":
        memory["project_id"] = None
    elif change == "condition_limit":
        memory["conditions"] = {f"condition-{i}": "test" for i in range(21)}
    elif change == "condition_key":
        memory["conditions"] = {"x" * 129: "test"}
    elif change == "content_limit":
        version["content"] = "x" * 8001
    elif change == "naive":
        version["valid_from"] = "2026-10-09T10:00:00"
    elif change == "zero":
        version["number"] = 0
    elif change == "bool":
        version["number"] = True
    elif change == "duplicate_memory":
        records[1]["memory"]["id"] = memory["id"]
    elif change == "duplicate_version":
        records[1]["memory"]["version"]["id"] = version["id"]
    elif change == "secret":
        version["content"] = "password=synthetic-sensitive-test-string"
    elif change == "secret_source":
        version["source"]["evidence"] = "password=synthetic-sensitive-test-string"
    elif change == "secret_condition":
        memory["conditions"] = {"password": "synthetic-sensitive-test-string"}
    elif change == "nonfinite":
        records[0]["confidence"] = float("nan")
    elif change == "tuple":
        records = tuple(records)
    elif change == "many":
        records *= 101
    elif change == "cycle":
        version["source"]["evidence"] = records
    else:
        version["content"] = "x" * (MAX_INPUT_CHARACTERS + 1)
    provider = Group()
    with pytest.raises(ModuleError) as exc:
        Consolidator(provider, Verify()).propose(records)
    assert str(exc.value) == "INVALID_INPUT"
    assert "sensitive" not in str(exc.value)
    assert provider.calls == []


@pytest.mark.parametrize(
    "raw",
    [
        "not JSON",
        "[]",
        '{"groups": [], "groups": []}',
        '{"groups": NaN}',
        '{"groups": [[1]]}',
        '{"groups": [[]]}',
        '{"groups": [], "summary": "guessed"}',
        '{"groups": [], "password": "synthetic-sensitive-test-string"}',
        None,
        "x" * (MAX_GROUPING_CHARACTERS + 1),
    ],
)
def test_invalid_grouping_is_safe_failure(record, raw):
    class Invalid:
        def group(self, records):
            return raw

    with pytest.raises(ModuleError, match="INVALID_PROVIDER_OUTPUT"):
        Consolidator(Invalid(), Verify()).propose(sources(record))


@pytest.mark.parametrize("mode", ["missing", "unknown", "repeat"])
def test_provider_cannot_drop_rare_sources_forge_versions_or_overlap_groups(record, mode):
    class Invalid(Group):
        def group(self, records):
            ids = [r["memory"]["version"]["id"] for r in records]
            groups = [ids[:1]] if mode == "missing" else [[str(uuid4()), ids[1]]]
            if mode == "repeat":
                groups = [ids, ids]
            return json.dumps({"groups": groups})

    with pytest.raises(ModuleError, match="INVALID_PROVIDER_OUTPUT"):
        Consolidator(Invalid(), Verify()).propose(sources(record))


def test_explicit_singletons_and_empty_groups_retain_originals(record):
    records = sources(record)
    for groups in ([], [[r["memory"]["version"]["id"]] for r in records]):
        module = Consolidator(RecordedGroupingProvider([(records, groups)]), Verify())
        assert module.propose(records) == []
    provider = Group()
    assert Consolidator(provider, Verify()).propose([]) == []
    assert Consolidator(provider, Verify()).propose(records[:1]) == []
    assert provider.calls == []


def test_large_summary_abstains_instead_of_truncating_and_refs_are_deduplicated(record):
    records = sources(record)
    records[1]["memory"]["version"]["source"] = deepcopy(records[0]["memory"]["version"]["source"])
    assert len(Consolidator(Group(), Verify()).propose(records)[0]["source_refs"]) == 1
    for r in records:
        r["memory"]["version"]["content"] = "Rare complete text. " * 250
    verifier = Verify()
    assert Consolidator(Group(), verifier).propose(records) == []
    assert verifier.calls == []


@pytest.mark.parametrize("phase", ["group", "verify"])
@pytest.mark.parametrize(
    "error,code,retryable",
    [
        (TimeoutError("private upstream text"), "PROVIDER_UNAVAILABLE", True),
        (ConnectionError("private upstream text"), "PROVIDER_UNAVAILABLE", True),
        (RuntimeError("private upstream text"), "INVALID_PROVIDER_OUTPUT", False),
    ],
)
def test_provider_errors_do_not_expose_text_or_partial_results(
    record, phase, error, code, retryable
):
    class Failure(Group, Verify):
        def group(self, records):
            if phase == "group":
                raise error
            return super().group(records)

        def verify(self, proposal, records):
            raise error

    failure = Failure()
    with pytest.raises(ModuleError) as exc:
        Consolidator(failure, failure).propose(sources(record))
    assert str(exc.value) == code and exc.value.retryable is retryable


def test_invalid_verdict_and_unknown_fixture_are_not_supported(record):
    records = sources(record)
    with pytest.raises(ModuleError, match="INVALID_PROVIDER_OUTPUT"):
        Consolidator(Group(), Verify(True)).propose(records)
    assert Consolidator(Group(), RecordedConsolidationVerifier([])).propose(records) == []


def test_provider_mutation_cannot_change_input_summary_or_provenance(record):
    class Mutation(Group):
        def group(self, records):
            output = super().group(records)
            records[0]["memory"]["version"]["content"] = "invented meaning"
            return output

    class MutatingVerifier(Verify):
        def verify(self, proposal, records):
            proposal["summary"] = "invented summary"
            records[0]["memory"]["project_id"] = "another-project"
            return "supported"

    records = sources(record)
    before = deepcopy(records)
    proposal = Consolidator(Mutation(), MutatingVerifier()).propose(records)[0]
    assert records == before
    assert "invented" not in proposal["summary"]
    assert proposal["project_id"] == record["memory"]["project_id"]


def test_repeated_claim_is_compacted_but_every_source_is_cited_and_rare_fact_survives(record):
    records = sources(record)
    repeated = deepcopy(records[0])
    repeated["memory"]["id"], repeated["memory"]["version"]["id"] = str(uuid4()), str(uuid4())
    records.append(repeated)
    records[1]["confidence"] = None  # Explicit evidence needs no model confidence or repetition.
    proposal = Consolidator(Group(), Verify()).propose(records)[0]
    assert proposal["summary"].count(records[0]["memory"]["version"]["content"]) == 1
    assert records[1]["memory"]["version"]["content"] in proposal["summary"]
    assert len(proposal["source_version_ids"]) == 3


def test_more_than_twenty_proposals_is_rejected_without_truncating_rare_groups(record):
    records = []
    for index in range(21):
        for item in sources(record):
            item["memory"]["id"], item["memory"]["version"]["id"] = str(uuid4()), str(uuid4())
            item["memory"]["conditions"] = {"environment": f"test-{index}"}
            records.append(item)
    with pytest.raises(ModuleError, match="INVALID_PROVIDER_OUTPUT"):
        Consolidator(Group(), Verify()).propose(records)


def test_later_provider_failure_does_not_return_an_earlier_valid_proposal(record):
    class LaterFailure(Verify):
        def verify(self, proposal, records):
            if self.calls:
                raise TimeoutError("private second-group detail")
            return super().verify(proposal, records)

    records = sources(record)
    for item in sources(record):
        item["memory"]["id"], item["memory"]["version"]["id"] = str(uuid4()), str(uuid4())
        item["memory"]["conditions"] = {"env": "other"}
        records.append(item)
    with pytest.raises(ModuleError, match="PROVIDER_UNAVAILABLE") as exc:
        Consolidator(Group(), LaterFailure()).propose(records)
    assert exc.value.retryable is True

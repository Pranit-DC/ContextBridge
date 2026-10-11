from copy import deepcopy
from uuid import uuid4

import pytest

from contextbridge.contracts import CapturedEvent, RetrievalQuery
from contextbridge.engine.errors import ModuleError
from contextbridge.engine.modules import ModuleGateway
from tests.engine.fakes import FakeExtractor, FakeRepository, FakeRetriever, fixture


def test_missing_provider_is_distinct_from_empty_extraction():
    event = CapturedEvent.model_validate(fixture("captured-event"))
    with pytest.raises(ModuleError) as error:
        ModuleGateway().extract(event)
    assert error.value.code == "PROVIDER_UNAVAILABLE"

    class EmptyExtractor:
        def extract(self, event):
            return []

    assert ModuleGateway(extractor=EmptyExtractor()).extract(event) == []


def test_injected_extractor_preserves_evidence_and_receives_dictionary_contract():
    provider = FakeExtractor()
    event = CapturedEvent.model_validate(fixture("captured-event"))
    candidate = ModuleGateway(extractor=provider).extract(event)[0]
    assert provider.calls == [fixture("captured-event")]
    assert candidate.source.evidence == event.messages[0].content


@pytest.mark.parametrize(
    "mutation", ["scope", "reference", "excerpt", "secret", "duplicate", "agent"]
)
def test_untrusted_provider_output_is_rechecked(mutation):
    class BadExtractor:
        def extract(self, event):
            value = fixture("candidate")
            if mutation == "scope":
                value["project_id"] = "unrelated"
            elif mutation == "reference":
                value["evidence_refs"][0]["message_id"] = "missing"
            elif mutation == "excerpt":
                value["source"]["evidence"] = "Invented quotation."
            elif mutation == "secret":
                value["content"] = "password=private-value"
            elif mutation == "agent":
                value["source"]["agent"] = "another-agent"
            return [value, deepcopy(value)] if mutation == "duplicate" else [value]

    event = CapturedEvent.model_validate(fixture("captured-event"))
    with pytest.raises(ModuleError) as error:
        ModuleGateway(extractor=BadExtractor()).extract(event)
    assert error.value.code == "INVALID_PROVIDER_OUTPUT"
    assert "private-value" not in str(error.value)


def test_assistant_cannot_supply_authoritative_evidence():
    event = fixture("captured-event")
    event["messages"][0]["role"] = "assistant"
    with pytest.raises(ModuleError):
        ModuleGateway(extractor=FakeExtractor()).extract(CapturedEvent.model_validate(event))


def test_recognized_credentials_never_reach_extractor():
    provider = FakeExtractor()
    event = fixture("captured-event")
    event["messages"][0]["content"] = "password=private-value"
    with pytest.raises(ModuleError) as error:
        ModuleGateway(extractor=provider).extract(CapturedEvent.model_validate(event))
    assert error.value.code == "INVALID_INPUT"
    assert provider.calls == []


@pytest.mark.parametrize(
    ("failure", "code", "retryable"),
    [
        (TimeoutError("private-text"), "PROVIDER_UNAVAILABLE", True),
        (RuntimeError("private-text"), "INVALID_PROVIDER_OUTPUT", False),
        (ModuleError("EMBEDDING_UNAVAILABLE", retryable=True), "EMBEDDING_UNAVAILABLE", True),
    ],
)
def test_provider_failures_are_safe_and_only_transient_errors_retry(failure, code, retryable):
    class FailedExtractor:
        def extract(self, event):
            raise failure

    with pytest.raises(ModuleError) as error:
        ModuleGateway(extractor=FailedExtractor()).extract(
            CapturedEvent.model_validate(fixture("captured-event"))
        )
    assert (error.value.code, error.value.retryable) == (code, retryable)
    assert "private-text" not in str(error.value)


def test_retriever_uses_resolved_time_and_checks_final_liveness():
    query = fixture("retrieval-snapshot")["query"]
    query["as_of"] = None
    repo = FakeRepository()
    result = ModuleGateway(retriever=FakeRetriever()).search(
        RetrievalQuery.model_validate(query), repo, None, None
    )
    assert len(result.cards) == 1
    assert repo.checks[0][1]["as_of"] is not None
    with pytest.raises(ModuleError):
        ModuleGateway(retriever=FakeRetriever()).search(
            RetrievalQuery.model_validate(query), FakeRepository(live=False), None, None
        )


@pytest.mark.parametrize("mutation", ["scope", "conditions", "time", "duplicate", "limit"])
def test_retrieval_boundary_rejects_ineligible_results(mutation):
    class BadRetriever:
        def search(self, query, repository, embedder, verifier):
            value = fixture("retrieval-result")
            card = value["cards"][0]
            if mutation == "scope":
                card["project_id"] = "unrelated"
            elif mutation == "conditions":
                card["conditions"] = {"environment": "production"}
            elif mutation == "time":
                card["valid_to"] = "2026-10-09T10:30:00Z"
            elif mutation in {"duplicate", "limit"}:
                second = deepcopy(card)
                if mutation == "limit":
                    second["version_id"] = str(uuid4())
                value["cards"].append(second)
            return value

    query = fixture("retrieval-snapshot")["query"]
    query["limit"] = 1 if mutation == "limit" else 3
    with pytest.raises(ModuleError):
        ModuleGateway(retriever=BadRetriever()).search(
            RetrievalQuery.model_validate(query), FakeRepository(), None, None
        )

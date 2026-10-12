"""Real PostgreSQL engine commits only candidates passing the explicit source audits."""

import json

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from contextbridge.engine.modules import ModuleGateway
from contextbridge.engine.write import WriteEngine
from contextbridge.formation import AdmissionPolicy, Extractor
from contextbridge.formation.providers.chat import ChatClient
from contextbridge.formation.providers.grounded import BatchVerifier, GroundedProvider
from contextbridge.formation.providers.recorded import RecordedEvidenceVerifier, RecordedProvider
from contextbridge.models import Memory, MemoryVersion
from tests.formation.test_engine_integration import setup
from tests.formation.test_groq_provider import settings as groq_settings
from tests.formation.test_grounded_provider import check, wire
from tests.formation.test_occurrence_grounding import OCCURRENCE, UNCONFIRMED, uncertain_event

pytestmark = pytest.mark.integration


def test_wholly_speculative_local_abstention_is_durably_pending(database, event, candidate):
    event["messages"][0]["content"] = (
        f"{event['project_id']} might use SQLite someday; "
        "there is no agreed choice or effective date."
    )
    configured, _, job = setup(database, event, candidate)
    requests = []
    client = ChatClient(
        groq_settings(), transport=httpx.MockTransport(lambda r: requests.append(r))
    )
    verifier = BatchVerifier(client)
    modules = ModuleGateway(
        extractor=Extractor(GroundedProvider(client), verifier, admission_checks=True)
    )
    with Session(database[1], expire_on_commit=False) as db:
        result = WriteEngine(db, configured, modules).process(job)
        assert result.status == "deferred" and result.reason_codes == ["INSUFFICIENT_EVIDENCE"]
        assert WriteEngine(db, configured, modules).process(job).status == "deferred"
        assert db.scalar(select(func.count()).select_from(Memory)) == 0
    assert requests == []


def completed_response(value):
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": json.dumps(value)},
                }
            ]
        },
    )


@pytest.mark.parametrize("fault", ["none", "excluded_project", "missing_conditions", "wrong_kind"])
def test_grounded_adapters_obey_shared_engine_write_boundary(database, event, candidate, fault):
    if fault == "excluded_project":
        event["messages"][0]["content"] = (
            f"The unnamed other repo uses MySQL; it is not {event['project_id']}."
        )
        candidate["source"]["evidence"] = "The unnamed other repo uses MySQL"
        candidate["content"] = "The other repository uses MySQL."
    configured, _, job = setup(database, event, candidate)

    def handler(request):
        name = json.loads(request.content)["response_format"]["json_schema"]["name"]
        changes = (
            {"conditions": [{"key": "version", "value": "V9"}]}
            if fault == "missing_conditions"
            else {"kind": "FACT" if candidate["type"] != "FACT" else "DECISION"}
            if fault == "wrong_kind"
            else {}
        )
        value = (
            {"claims": [wire(candidate)]}
            if name == "Claims"
            else {"checks": [check(candidate, **changes)]}
        )
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": json.dumps(value)},
                    }
                ]
            },
        )

    client = ChatClient(groq_settings(), transport=httpx.MockTransport(handler))
    verifier = BatchVerifier(client)
    modules = ModuleGateway(
        extractor=Extractor(GroundedProvider(client), verifier),
        admission=AdmissionPolicy(verifier, lambda _: event),
    )
    with Session(database[1], expire_on_commit=False) as session:
        result = WriteEngine(session, configured, modules).process(job)
        assert bool(result.memory_ids) == (fault == "none")
        assert session.scalar(select(func.count()).select_from(Memory)) == int(fault == "none")


@pytest.mark.parametrize("entry", ["extraction", "admission"])
@pytest.mark.parametrize("wording", UNCONFIRMED)
def test_uncertain_occurrences_never_reach_shared_engine_storage(
    database, event, candidate, entry, wording
):
    uncertain_event(event, candidate, wording)
    configured, _, job = setup(database, event, candidate)
    stages = []

    def handler(request):
        schema = json.loads(request.content)["response_format"]["json_schema"]["name"]
        stages.append(schema)
        value = (
            {"claims": [wire(candidate)]}
            if schema == "Claims"
            else {"checks": [check(candidate, kind="STATE")]}
        )
        return completed_response(value)

    client = ChatClient(groq_settings(), transport=httpx.MockTransport(handler))
    verifier = BatchVerifier(client)
    extractor = (
        Extractor(GroundedProvider(client), verifier)
        if entry == "extraction"
        else Extractor(
            RecordedProvider(event, json.dumps([candidate])),
            RecordedEvidenceVerifier([(event, candidate, "supported")]),
        )
    )
    modules = ModuleGateway(
        extractor=extractor,
        admission=AdmissionPolicy(verifier, lambda _: event),
    )
    with Session(database[1], expire_on_commit=False) as session:
        result = WriteEngine(session, configured, modules).process(job)
        assert result.memory_ids == []
        assert session.scalar(select(func.count()).select_from(Memory)) == 0
    assert stages == (["Claims", "Checks"] if entry == "extraction" else ["Checks"])


def test_positive_dated_occurrence_still_commits_correct_category_and_source_time(
    database, event, candidate
):
    uncertain_event(event, candidate, "completed")
    configured, _, job = setup(database, event, candidate)

    def handler(request):
        schema = json.loads(request.content)["response_format"]["json_schema"]["name"]
        value = (
            {"claims": [wire(candidate)]} if schema == "Claims" else {"checks": [check(candidate)]}
        )
        return completed_response(value)

    client = ChatClient(groq_settings(), transport=httpx.MockTransport(handler))
    verifier = BatchVerifier(client)
    modules = ModuleGateway(
        extractor=Extractor(GroundedProvider(client), verifier),
        admission=AdmissionPolicy(verifier, lambda _: event),
    )
    with Session(database[1], expire_on_commit=False) as session:
        result = WriteEngine(session, configured, modules).process(job)
        assert len(result.memory_ids) == 1
        memory = session.scalar(select(Memory))
        assert memory.type == "EVENT"
        version = session.scalar(select(MemoryVersion))
        assert version.valid_from.isoformat() == OCCURRENCE.replace("Z", "+00:00")
        assert version.content == candidate["content"]

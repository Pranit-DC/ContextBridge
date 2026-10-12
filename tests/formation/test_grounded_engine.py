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
from contextbridge.models import Memory
from tests.formation.test_engine_integration import setup
from tests.formation.test_groq_provider import settings as groq_settings
from tests.formation.test_grounded_provider import check, wire

pytestmark = pytest.mark.integration


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

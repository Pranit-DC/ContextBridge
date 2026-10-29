"""Selective evidence checks through current adapters; no live HTTP 400 resolution claim."""

import json

import httpx
import pytest
from sqlalchemy.orm import Session

from contextbridge.contracts import RetrievalQuery
from contextbridge.engine.errors import ModuleError
from contextbridge.engine.retrieval import RetrievalService
from scripts.v1.budget import BudgetTransport
from tests.integration.phase4_fakes import HostedReplay
from tests.integration.retrieval_fakes import create, query
from tests.integration.write_fakes import Harness

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    "judgment", ["supports", "contradicts", "insufficient", "http400", "malformed", "timeout"]
)
def test_selective_judgment_and_failure_keep_safe_uncertainty_labels(
    database, monkeypatch, tmp_path, judgment
):
    memory = create(database, "Use PostgreSQL database.")
    harness = Harness(database)

    def respond(name, value):
        assert name == "JudgmentResponse"
        assert value == {
            "claim": memory.version.content,
            "evidence": memory.version.source.evidence,
        }
        if judgment == "http400":
            return httpx.Response(
                400, json={"error": "synthetic-provider-diagnostic-must-not-escape"}
            )
        if judgment == "timeout":
            raise httpx.ReadTimeout("synthetic-provider-diagnostic-must-not-escape")
        return {"judgment": "invalid" if judgment == "malformed" else judgment}

    replay = HostedReplay(harness, monkeypatch, tmp_path, respond)
    with Session(database[1]) as db:
        result = RetrievalService(
            db, harness.settings, replay.providers.modules, verifier=replay.providers.verifier
        ).search(RetrievalQuery.model_validate(query()))
    assert len(result.cards) == 1 and result.cards[0].memory_id == memory.id
    assert result.cards[0].verification == ("supported" if judgment == "supports" else "uncertain")
    failure = judgment in {"http400", "malformed", "timeout"}
    assert ("VERIFICATION_UNAVAILABLE" in result.warnings) == failure
    assert "synthetic-provider-diagnostic" not in json.dumps(result.model_dump(mode="json"))
    assert replay.snapshot() == {
        "calls": {"groq": 1, "cloudflare": 0},
        "stopped": judgment in {"http400", "timeout"},
    }
    if judgment in {"http400", "timeout"}:

        def forbidden(request):
            raise AssertionError("The stopped ledger must block both provider routes")

        with pytest.raises(ModuleError, match="CANCELLED"):
            BudgetTransport(
                replay.ledger_path, "cloudflare", transport=httpx.MockTransport(forbidden)
            ).handle_request(httpx.Request("POST", "https://synthetic.invalid"))
        assert len(replay.requests) == 1

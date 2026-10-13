import json
import sys
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from contextbridge.formation.providers.config import FormationSettings
from contextbridge.retrieval.cloudflare import MODEL_ID
from scripts import check_v1_providers as check
from scripts.v1.budget import BudgetTransport, Ledger


@pytest.mark.parametrize("groq_status", [200, 429])
def test_connectivity_check_is_three_requests_at_most_and_never_resumes(
    tmp_path, monkeypatch, groq_status
):
    formation = FormationSettings(
        _env_file=None,
        provider="openai-compatible",
        model="openai/gpt-oss-120b",
        base_url="https://api.groq.com/openai/v1",
        api_key="synthetic-secret-key",
    )
    settings = SimpleNamespace(
        embedding_provider="cloudflare",
        embedding_api_key=SecretStr("synthetic-secret-key"),
        embedding_base_url=SecretStr(
            "https://api.cloudflare.com/client/v4/accounts/" + "0" * 32 + "/ai/v1"
        ),
        embedding_model_id=MODEL_ID,
        embedding_dimensions=1024,
        retrieval_min_similarity=0.4,
    )
    monkeypatch.setattr(check, "Settings", lambda: settings)
    monkeypatch.setattr(check, "FormationSettings", lambda: formation)
    requests = []

    def handle(request):
        requests.append(request)
        if request.url.host == "api.groq.com":
            return httpx.Response(
                groq_status,
                json={
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": '{"judgment":"supports"}'},
                        }
                    ]
                },
            )
        body = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": i, "embedding": [1.0] + [0.0] * 1023}
                    for i in range(len(body["input"]))
                ]
            },
        )

    monkeypatch.setattr(
        check,
        "BudgetTransport",
        lambda path, provider: BudgetTransport(
            path, provider, transport=httpx.MockTransport(handle)
        ),
    )
    path = tmp_path / "ledger.sqlite"
    report = tmp_path / "report.json"
    argv = ["check", "--ledger", str(path), "--report", str(report), "--free-groq-confirmed"]
    monkeypatch.setattr(sys, "argv", argv)
    assert check.main() == (0 if groq_status == 200 else 1)
    assert Ledger(path).snapshot()["calls"] == {
        "groq": 1,
        "cloudflare": 2 if groq_status == 200 else 0,
    }
    assert len(requests) == (3 if groq_status == 200 else 1)
    # A competing check may have claimed the file before reserving its first request.
    reserved = tmp_path / "reserved.sqlite"
    reserved.with_name(reserved.name + ".started").touch()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check",
            "--ledger",
            str(reserved),
            "--report",
            str(tmp_path / "reserved-report.json"),
            "--free-groq-confirmed",
        ],
    )
    with pytest.raises(SystemExit):
        check.main()
    assert Ledger(reserved).snapshot()["calls"] == {"groq": 0, "cloudflare": 0}
    assert len(requests) == (3 if groq_status == 200 else 1)
    assert "synthetic-secret-key" not in report.read_text()
    # Preserve the used ledger; a fresh output filename cannot resume it.
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check",
            "--ledger",
            str(path),
            "--report",
            str(tmp_path / "another-report.json"),
            "--free-groq-confirmed",
        ],
    )
    with pytest.raises(SystemExit):
        check.main()
    assert len(requests) == (3 if groq_status == 200 else 1)

"""Compact-profile CLI and telemetry checks use HTTP fixtures, not real model quality."""

import json

import httpx
import pytest

from contextbridge.engine.errors import ModuleError
from contextbridge.formation.providers.chat import ChatClient
from contextbridge.formation.providers.quota import TokenGate
from scripts.formation import evaluate, verify_groq
from scripts.formation.execution import ExecutionTelemetry, summarize_execution
from tests.formation.test_groq_execution import arguments
from tests.formation.test_groq_provider import Clock, settings
from tests.formation.test_grounded_provider import check, wire


def test_v4_cli_has_one_audit_for_two_claims_and_unchanged_contracts(monkeypatch, tmp_path):
    dataset, digest = evaluate.load_dataset("tuning", root=evaluate.ROOT / "fresh-v2-20261012")
    clock, requests = Clock(), []
    monkeypatch.setattr(verify_groq, "load_settings", settings)
    monkeypatch.setattr(
        verify_groq,
        "TokenGate",
        lambda **kw: TokenGate(clock=clock.clock, sleeper=clock.sleep, **kw),
    )
    lease = verify_groq.evaluation_lease
    monkeypatch.setattr(verify_groq, "evaluation_lease", lambda _: lease(tmp_path / "fixture.lock"))
    original = ChatClient.__init__

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        payload = json.loads(body["messages"][1]["content"])
        schema = body["response_format"]["json_schema"]["name"]
        if schema == "DuplicateResponse":
            result = {"relation": "equivalent"}
            assert body["max_completion_tokens"] == 256
        else:
            event = payload if schema == "Claims" else payload["event"]
            case = next(
                c
                for c in dataset.cases
                if c.event.model_dump(mode="json")["messages"] == event["messages"]
            )
            candidates = [
                evaluate.fixture_candidate(case, c).model_dump(mode="json")
                for c in case.expected_claims
            ]
            result = (
                {"claims": [wire(c) for c in candidates]}
                if schema == "Claims"
                else {"checks": [check(c, index=i) for i, c in enumerate(candidates)]}
            )
        return httpx.Response(
            200,
            json={
                "model": "openai/gpt-oss-120b",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": json.dumps(result)},
                    }
                ],
                "usage": {"prompt_tokens": 300, "completion_tokens": 200},
            },
        )

    monkeypatch.setattr(
        ChatClient,
        "__init__",
        lambda self, configured: original(self, configured, transport=httpx.MockTransport(handler)),
    )
    path = tmp_path / "run.json"
    arguments(
        monkeypatch,
        path,
        "--profile",
        "v4",
        "--dataset-revision",
        "fresh-v2",
        "--approved-conventions",
    )
    assert verify_groq.main() == 0
    run = evaluate.decode(evaluate.Run, evaluate.read_payload(path))
    sidecar = evaluate.decode(
        ExecutionTelemetry, evaluate.read_payload(path.with_suffix(".telemetry.json"))
    )
    execution = summarize_execution(dataset, digest, run, sidecar)
    assert execution["case_counts"]["completed_network_cases"] == 9
    assert execution["case_counts"]["local_only_cases"] == 3
    assert execution["case_counts"]["scope_abstention_cases"] == 1
    assert execution["case_counts"]["uncertain_abstention_cases"] == 1
    multi = next(c for c in dataset.cases if len(c.expected_claims) == 2)
    assert (
        len([c for c in sidecar.calls if c.case_id == multi.case_id and c.stage == "verification"])
        == 1
    )
    assert len(next(c for c in run.cases if c.case_id == multi.case_id).decisions) == 2
    assert run.metadata.configuration["verification_mode"] == "batch"
    assert all(c.cost_usd is None for c in sidecar.calls)
    run.metadata.configuration.pop("verification_mode")
    sidecar.run_sha256 = evaluate.dataset_digest(run)
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        summarize_execution(dataset, digest, run, sidecar)


def test_batch_hook_checks_all_source_refs_before_any_verification(event, candidate):
    from contextbridge.formation import Extractor
    from contextbridge.formation.providers.recorded import RecordedProvider

    class Uncalled:
        def prepare(self, *_):
            pytest.fail("Forged evidence must fail locally before batch verification")

    candidate["evidence_refs"][0]["message_id"] = "missing"
    with pytest.raises(ModuleError, match="INVALID_PROVIDER_OUTPUT"):
        Extractor(RecordedProvider(event, json.dumps([candidate])), Uncalled()).extract(event)


def test_fresh_splits_are_disjoint_and_do_not_change_legacy_fingerprints():
    root = evaluate.ROOT / "fresh-v2-20261012"
    tuning, _ = evaluate.load_dataset("tuning", root=root)
    holdout, _ = evaluate.load_dataset("holdout", root=root)
    evaluate.validate_splits(tuning, holdout)
    _, legacy = evaluate.load_dataset("holdout")
    assert legacy == "ad6038dfd2f8f0b0ef625f40da9743e5519426ab7b61bfc23154d158ae32ac7f"
    assert not {c.event.event_id for c in tuning.cases} & {c.event.event_id for c in holdout.cases}


def test_partial_invalid_generation_never_exports_unreturned_corrections():
    from contextbridge.formation.providers.bounded import QuotaClient
    from contextbridge.formation.providers.grounded import BatchVerifier, GroundedProvider
    from scripts.formation.verify_free import measure

    dataset, _ = evaluate.load_dataset("tuning", root=evaluate.ROOT / "fresh-v2-20261012")
    case = next(c for c in dataset.cases if c.case_id.endswith("current-status"))
    dataset.cases = [case]
    digest = evaluate.dataset_digest(dataset)
    candidate = evaluate.fixture_candidate(case, case.expected_claims[0]).model_dump(mode="json")
    first = wire(candidate) | {"kind": "FACT"}
    invalid = first | {"message_id": "unknown"}
    payload = {"claims": [first, invalid]}
    clock = Clock()

    def factory(*args, **kw):
        return QuotaClient(
            *args,
            **kw,
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    200,
                    json={
                        "model": "openai/gpt-oss-120b",
                        "choices": [{"message": {"content": json.dumps(payload)}}],
                        "usage": {"prompt_tokens": 300, "completion_tokens": 200},
                    },
                )
            ),
        )

    calls, cases = [], []
    predictions, count = measure(
        dataset,
        settings(),
        4,
        telemetry=calls,
        case_telemetry=cases,
        gate=TokenGate(clock=clock.clock, sleeper=clock.sleep, smooth=True),
        client_factory=factory,
        provider_factory=GroundedProvider,
        verifier_factory=BatchVerifier,
    )
    assert count == 1
    assert predictions[0].error_code == "INVALID_PROVIDER_OUTPUT"
    assert predictions[0].proposals == []
    assert "type_corrections" not in cases[0]
    run = evaluate.Run(
        schema_version=1,
        mode="model_predictions",
        split="tuning",
        dataset_sha256=digest,
        metadata=evaluate.Metadata(
            provider_id="fixture",
            model_id="openai/gpt-oss-120b",
            prompt_version="fixture",
            recorded_at=case.context.checked_at,
            configuration={},
            cost_currency="USD",
        ),
        cases=predictions,
    )
    sidecar = evaluate.decode(
        ExecutionTelemetry,
        json.dumps(
            {
                "schema_version": 1,
                "dataset_sha256": digest,
                "run_sha256": evaluate.dataset_digest(run),
                "prompt_version": "fixture",
                "calls": calls,
                "cases": cases,
                "execution": {
                    "concurrency": 1,
                    "request_interval_seconds": 3.1,
                    "max_calls": 4,
                    "automatic_retries": 0,
                    "stop_on_provider_unavailable": True,
                },
            }
        ).encode(),
    )
    execution = summarize_execution(dataset, digest, run, sidecar)
    assert execution["case_counts"]["attempted_failed_network_cases"] == 1

"""Evaluate only fixed synthetic O4 records through real injected Groq adapters; no storage."""

import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from contextbridge.engine.errors import ModuleError
from contextbridge.formation import Consolidator
from contextbridge.formation.providers.chat import contains_key
from contextbridge.formation.providers.config import GROQ_ENDPOINT, load_settings
from contextbridge.formation.providers.quota import TokenGate
from contextbridge.formation.providers.semantic import (
    CONSOLIDATION_PROMPT,
    CONSOLIDATION_PROMPT_VERSION,
    GROUPING_PROMPT,
    ChatConsolidationVerifier,
    ChatGroupingProvider,
)
from contextbridge.security import contains_secret_fields
from scripts.formation.demo_consolidation import load_cases
from scripts.formation.verify_free import evaluation_lease
from scripts.formation.verify_groq import GroqClient


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-free-plan", action="store_true")
    parser.add_argument("--max-calls", type=int, choices=range(1, 25), default=24)
    parser.add_argument("--tokens-per-minute", type=int, default=8000)
    parser.add_argument("--max-total-tokens", type=int, default=40000)
    args = parser.parse_args()
    try:
        original = load_settings()
        if not (
            args.execute
            and args.confirm_free_plan
            and not original.allow_paid
            and original.base_url == GROQ_ENDPOINT
        ):
            raise ModuleError("INVALID_INPUT")
        if args.output.exists() or not args.output.parent.is_dir():
            raise ModuleError("INVALID_INPUT")
        settings = type(original)(
            _env_file=None,
            **(
                original.model_dump()
                | {
                    "api_key": original.api_key,
                    "provider": "openai-compatible",
                    "model": "openai/gpt-oss-120b",
                    "verifier_model": "openai/gpt-oss-120b",
                    "allow_hosted": True,
                    "groq_free_plan_confirmed": True,
                }
            ),
        )
        settings.check_execution()
        cases = load_cases()
        digest = hashlib.sha256(
            json.dumps(cases, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        gate = TokenGate(
            tokens_per_minute=args.tokens_per_minute, max_total_tokens=args.max_total_tokens
        )
        calls, results = [], []
        lease = Path(__file__).resolve().parents[2] / ".pytest_cache/formation/free-evaluation.lock"
        with evaluation_lease(lease):
            for case in cases:
                first = len(calls)
                error, proposals = None, []
                grouping = GroqClient(
                    settings, calls, args.max_calls, case_id=case["id"], stage="grouping", gate=gate
                )
                verification = GroqClient(
                    settings,
                    calls,
                    args.max_calls,
                    case_id=case["id"],
                    stage="consolidation_verification",
                    gate=gate,
                )
                started = time.monotonic()
                try:
                    proposals = Consolidator(
                        ChatGroupingProvider(grouping), ChatConsolidationVerifier(verification)
                    ).propose(case["records"])
                except ModuleError as exc:
                    error = exc.code
                results.append(
                    {
                        "case_id": case["id"],
                        "proposals": proposals,
                        "error_code": error,
                        "attempted_calls": len(calls) - first,
                        "execution": (
                            "attempted"
                            if len(calls) > first
                            else "provider_stop"
                            if error == "PROVIDER_UNAVAILABLE"
                            else "token_budget"
                            if error == "CANCELLED" and gate.token_stopped
                            else "call_budget"
                            if error == "CANCELLED"
                            else "local_only"
                        ),
                        "latency_ms": (time.monotonic() - started) * 1000
                        if len(calls) > first
                        else None,
                        "design_expected_proposals": case["expected_proposals"],
                    }
                )
                print(
                    json.dumps(
                        {
                            "case_id": case["id"],
                            "error_code": error,
                            "calls": len(calls) - first,
                            "proposals": len(proposals),
                        }
                    ),
                    flush=True,
                )
        safe_calls = []
        for index, call in enumerate(calls, 1):
            observation = call["observation"]
            safe_calls.append(
                {
                    "call_index": index,
                    **{key: value for key, value in call.items() if key != "observation"},
                    "observed_model": observation.model if observation else None,
                    "input_tokens": observation.input_tokens if observation else None,
                    "output_tokens": observation.output_tokens if observation else None,
                    "cost_usd": observation.cost_usd if observation else None,
                    "http_status": observation.http_status if observation else None,
                    "provider_error_code": observation.provider_error_code if observation else None,
                }
            )
        public = settings.public_configuration()
        public.pop("api_key_configured")
        public["free_plan_evidence"] = "operator_attestation_not_api_verified"
        artifact = {
            "schema_version": 1,
            "kind": "synthetic_consolidation_predictions",
            "dataset_sha256": digest,
            "recorded_at": datetime.now(UTC).isoformat(),
            "model_id": settings.model,
            "prompt_version": CONSOLIDATION_PROMPT_VERSION,
            "prompt_sha256": {
                "grouping": hashlib.sha256(GROUPING_PROMPT.encode()).hexdigest(),
                "verification": hashlib.sha256(CONSOLIDATION_PROMPT.encode()).hexdigest(),
            },
            "configuration": public,
            "cases": results,
            "calls": safe_calls,
            "memory_saved": False,
            "label_status": "design_labels_independent_review_pending",
            "quality_gate": "pending",
            "execution": {
                "max_calls": args.max_calls,
                "tokens_per_minute": args.tokens_per_minute,
                "max_total_tokens": args.max_total_tokens,
                "concurrency": 1,
                "automatic_retries": 0,
            },
        }
        if contains_secret_fields(artifact) or contains_key(
            artifact, settings.api_key.get_secret_value()
        ):
            raise ModuleError("INVALID_PROVIDER_OUTPUT")
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(artifact, stream, indent=2)
        print(
            json.dumps(
                {"model_calls": len(calls), "memory_saved": False, "quality_gate": "pending"}
            )
        )
        return 0
    except (ModuleError, OSError, ValueError, TypeError, RecursionError):
        print(json.dumps({"error": "SAFE_VERIFICATION_FAILURE"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

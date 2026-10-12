"""Bounded synthetic Groq evaluation; operator-confirmed free plan, never memory writes."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from contextbridge.engine.errors import ModuleError
from contextbridge.formation.providers import conventions
from contextbridge.formation.providers.chat import PROMPT_VERSION, contains_key
from contextbridge.formation.providers.config import GROQ_ENDPOINT, GROQ_FREE_MODELS, load_settings
from contextbridge.formation.providers.quota import TokenGate, reservation
from contextbridge.formation.providers.semantic import ChatDuplicateVerifier
from contextbridge.security import contains_secret_fields
from scripts.formation.evaluate import Metadata, Run, dataset_digest, load_dataset
from scripts.formation.verify_free import (
    BoundedClient,
    CapturingProvider,
    OnceVerifier,
    evaluation_lease,
    measure,
)


class ConventionalProvider(CapturingProvider):
    def __init__(self, client):
        super().__init__(client)
        self.prompt = conventions.EXTRACTION
        self.condition_aliases = {"project_version": "version"}


class ConventionalVerifier(OnceVerifier):
    def __init__(self, client):
        super().__init__(client)
        self.prompt = conventions.VERIFICATION


class GroqClient(BoundedClient):
    def _complete(self, model, prompt, payload, schema):
        if len(self.calls) >= self.max_calls:
            raise ModuleError("CANCELLED")
        self.gate.pending_tokens = reservation(self.settings, prompt, payload, schema)
        before = len(self.calls)
        try:
            return super()._complete(model, prompt, payload, schema)
        finally:
            if len(self.calls) > before:
                self.calls[-1]["reserved_tokens"] = self.gate.pending_tokens
                self.gate.observe(self.last_observation)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=sorted(GROQ_FREE_MODELS), required=True)
    parser.add_argument("--split", choices=("tuning", "holdout"), default="tuning")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-free-plan", action="store_true")
    parser.add_argument("--approved-holdout", action="store_true")
    parser.add_argument("--approved-conventions", action="store_true")
    parser.add_argument("--max-calls", type=int, choices=range(1, 41), default=32)
    parser.add_argument("--tokens-per-minute", type=int, default=8000)
    parser.add_argument("--max-total-tokens", type=int, default=50000)
    args = parser.parse_args()
    try:
        original = load_settings()
        if not (
            args.execute
            and args.confirm_free_plan
            and not original.allow_paid
            and original.base_url == GROQ_ENDPOINT
            and (args.split != "holdout" or args.approved_holdout)
        ):
            raise ModuleError("INVALID_INPUT")
        # Explicit CLI consent/process settings; leave both env files untouched.
        settings = type(original)(
            _env_file=None,
            **(
                original.model_dump()
                | {
                    "api_key": original.api_key,
                    "provider": "openai-compatible",
                    "model": args.model,
                    "verifier_model": args.model,
                    "allow_hosted": True,
                    "groq_free_plan_confirmed": True,
                }
            ),
        )
        settings.check_execution()
        dataset, digest = load_dataset(args.split)
        telemetry_path = args.output.with_suffix(".telemetry.json")
        if args.output.exists() or telemetry_path.exists() or not args.output.parent.is_dir():
            raise ModuleError("INVALID_INPUT")
        gate = TokenGate(
            tokens_per_minute=args.tokens_per_minute, max_total_tokens=args.max_total_tokens
        )
        telemetry, cases = [], []
        lease = Path(__file__).resolve().parents[2] / ".pytest_cache/formation/free-evaluation.lock"
        options = {}
        prompt_version = PROMPT_VERSION
        if args.approved_conventions:
            options.update(
                provider_factory=ConventionalProvider,
                verifier_factory=ConventionalVerifier,
                policy_options_factory=lambda client: {
                    "duplicate_verifier": ChatDuplicateVerifier(client)
                },
            )
            prompt_version = conventions.PROMPT_VERSION
        with evaluation_lease(lease):
            predictions, calls = measure(
                dataset,
                settings,
                args.max_calls,
                telemetry=telemetry,
                case_telemetry=cases,
                gate=gate,
                client_factory=GroqClient,
                **options,
            )
        configuration = settings.public_configuration()
        configuration.pop("api_key_configured")
        configuration.update(free_plan_evidence="operator_attestation_not_api_verified")
        if args.approved_conventions:
            configuration.update(
                semantic_duplicate_verifier=True, condition_aliases="project_version=version"
            )
        run = Run(
            schema_version=1,
            mode="model_predictions",
            split=args.split,
            dataset_sha256=digest,
            metadata=Metadata(
                provider_id="groq",
                model_id=args.model,
                prompt_version=prompt_version,
                recorded_at=datetime.now(UTC),
                configuration=configuration,
                cost_currency="USD",
            ),
            cases=predictions,
        )
        sidecar = {
            "schema_version": 1,
            "dataset_sha256": digest,
            "run_sha256": dataset_digest(run),
            "prompt_version": prompt_version,
            "calls": telemetry,
            "cases": cases,
            "execution": {
                "concurrency": 1,
                "request_interval_seconds": 3.1,
                "max_calls": args.max_calls,
                "automatic_retries": 0,
                "stop_on_provider_unavailable": True,
                "tokens_per_minute": args.tokens_per_minute,
                "max_total_tokens": args.max_total_tokens,
            },
        }
        for artifact in (run.model_dump(mode="json"), sidecar):
            if contains_secret_fields(artifact) or contains_key(
                artifact, settings.api_key.get_secret_value()
            ):
                raise ModuleError("INVALID_PROVIDER_OUTPUT")
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(run.model_dump(mode="json"), stream, indent=2)
        with telemetry_path.open("x", encoding="utf-8") as stream:
            json.dump(sidecar, stream, indent=2)
        print(
            json.dumps(
                {
                    "model_calls": calls,
                    "memory_saved": False,
                    "human_review": "pending",
                    "quality_gate": "pending",
                }
            )
        )
        return 0
    except (ModuleError, OSError, ValueError, TypeError, RecursionError):
        print(json.dumps({"error": "SAFE_VERIFICATION_FAILURE"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

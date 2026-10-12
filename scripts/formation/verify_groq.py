"""Bounded synthetic Groq evaluation; operator-confirmed free plan, never memory writes."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from contextbridge.engine.errors import ModuleError
from contextbridge.formation.providers import conventions, grounded
from contextbridge.formation.providers.bounded import QuotaClient
from contextbridge.formation.providers.chat import PROMPT_VERSION, contains_key
from contextbridge.formation.providers.config import GROQ_ENDPOINT, GROQ_FREE_MODELS, load_settings
from contextbridge.formation.providers.quota import TokenGate
from contextbridge.formation.providers.semantic import ChatDuplicateVerifier
from contextbridge.security import contains_secret_fields
from scripts.formation.evaluate import ROOT, Metadata, Run, dataset_digest, load_dataset
from scripts.formation.verify_free import (
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


GroqClient = QuotaClient


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
    parser.add_argument("--profile", choices=("v3", "v4"), default="v3")
    parser.add_argument(
        "--dataset-revision", choices=("legacy", "fresh-v2", "fresh-v3"), default="legacy"
    )
    parser.add_argument("--extraction-output-tokens", type=int, default=1024)
    parser.add_argument("--verification-output-tokens", type=int, default=512)
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
        root = (
            ROOT
            if args.dataset_revision == "legacy"
            else ROOT / f"{args.dataset_revision}-20261012"
        )
        dataset, digest = load_dataset(args.split, root=root)
        telemetry_path = args.output.with_suffix(".telemetry.json")
        if args.output.exists() or telemetry_path.exists() or not args.output.parent.is_dir():
            raise ModuleError("INVALID_INPUT")
        gate = TokenGate(
            tokens_per_minute=args.tokens_per_minute,
            max_total_tokens=args.max_total_tokens,
            **({"smooth": True} if args.profile == "v4" else {}),
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
        if args.profile == "v4":
            if not args.approved_conventions or not all(
                128 <= value <= settings.max_output_tokens
                for value in (args.extraction_output_tokens, args.verification_output_tokens)
            ):
                raise ModuleError("INVALID_INPUT")

            def client_factory(configured, calls, max_calls, *, stage, **kw):
                limit = (
                    args.extraction_output_tokens
                    if stage == "extraction"
                    else min(args.verification_output_tokens, 256)
                    if stage == "comparison"
                    else args.verification_output_tokens
                )
                return GroqClient(
                    configured.model_copy(update={"max_output_tokens": limit}),
                    calls,
                    max_calls,
                    stage=stage,
                    **kw,
                )

            options.update(
                provider_factory=grounded.GroundedProvider,
                verifier_factory=grounded.BatchVerifier,
                client_factory=client_factory,
                policy_options_factory=lambda client: {
                    "duplicate_verifier": grounded.BoundedDuplicateVerifier(client)
                },
            )
            prompt_version = grounded.PROMPT_VERSION
        with evaluation_lease(lease):
            predictions, calls = measure(
                dataset,
                settings,
                args.max_calls,
                telemetry=telemetry,
                case_telemetry=cases,
                gate=gate,
                **({"client_factory": GroqClient} | options),
            )
        configuration = settings.public_configuration()
        configuration.pop("api_key_configured")
        configuration.update(free_plan_evidence="operator_attestation_not_api_verified")
        if args.approved_conventions:
            configuration.update(
                semantic_duplicate_verifier=True, condition_aliases="project_version=version"
            )
        if args.profile == "v4":
            configuration.update(
                verification_mode="batch",
                extraction_output_tokens=args.extraction_output_tokens,
                verification_output_tokens=args.verification_output_tokens,
                dataset_revision=args.dataset_revision,
                quota_profile="observed_input_estimates_smooth",
                scope_guard="explicit_exclusion",
                uncertainty_guard="no_adopted_choice",
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

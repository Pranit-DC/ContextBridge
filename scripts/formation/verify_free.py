"""Measure a configured free OpenRouter model on synthetic cases; never save memory."""

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from contextbridge.engine.errors import ModuleError
from contextbridge.formation import AdmissionPolicy, Extractor
from contextbridge.formation.providers.chat import (
    PROMPT_VERSION,
    ChatClient,
    ChatEvidenceVerifier,
    ChatModelProvider,
    contains_key,
)
from contextbridge.formation.providers.config import load_settings
from contextbridge.security import contains_secret_fields
from scripts.formation.evaluate import Metadata, Prediction, Run, load_dataset


class BoundedClient(ChatClient):
    def __init__(self, settings, calls, max_calls):
        super().__init__(settings)
        self.calls = calls
        self.max_calls = max_calls

    def complete(self, model, prompt, payload, schema):
        if len(self.calls) >= self.max_calls:
            raise ModuleError("CANCELLED")
        call = {"observation": None}
        self.calls.append(call)
        try:
            return super().complete(model, prompt, payload, schema)
        finally:
            call["observation"] = self.last_observation


class CapturingProvider(ChatModelProvider):
    def __init__(self, client):
        super().__init__(client)
        self.proposals = []

    def generate(self, event):
        raw = super().generate(event)
        # Capture valid source-bound proposals before semantic rejection for later review.
        self.proposals = json.loads(raw)
        return raw


class OnceVerifier(ChatEvidenceVerifier):
    def __init__(self, client):
        super().__init__(client)
        self.verdicts = {}

    def verify(self, candidate, event):
        key = json.dumps([candidate, event], sort_keys=True)
        if key not in self.verdicts:
            self.verdicts[key] = super().verify(candidate, event)
        return self.verdicts[key]


def measure(dataset, settings, max_calls):
    calls, predictions = [], []
    for case in dataset.cases:
        event = case.event.model_dump(mode="json")
        first_call = len(calls)
        provider = CapturingProvider(BoundedClient(settings, calls, max_calls))
        verifier = OnceVerifier(BoundedClient(settings, calls, max_calls))
        decisions, error = [], None
        started = time.monotonic()
        try:
            proposals = Extractor(provider, verifier).extract(event)
            policy = AdmissionPolicy(
                verifier,
                lambda event_id, event=event: event if event_id == event["event_id"] else None,
            )
            decisions = [
                policy.assess(candidate, case.context.model_dump(mode="json"))
                for candidate in proposals
            ]
        except ModuleError as exc:
            error = exc.code
            decisions = []
        observed = [call["observation"] for call in calls[first_call:]]

        def total(field, observed=observed):
            values = [getattr(item, field) if item else None for item in observed]
            return sum(values) if values and all(value is not None for value in values) else None

        predictions.append(
            Prediction(
                case_id=case.case_id,
                proposals=provider.proposals,
                decisions=decisions,
                error_code=error,
                latency_ms=(time.monotonic() - started) * 1000 if observed else None,
                input_tokens=total("input_tokens"),
                output_tokens=total("output_tokens"),
                cost=total("cost_usd"),
            )
        )
        print(
            json.dumps(
                {
                    "case_id": case.case_id,
                    "error_code": error,
                    "proposals": len(provider.proposals),
                    "calls": len(calls) - first_call,
                    "latency_seconds": round(time.monotonic() - started, 3),
                }
            ),
            flush=True,
        )
    return predictions, len(calls)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("tuning", "holdout"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--max-calls", type=int, default=24, choices=range(1, 41))
    args = parser.parse_args()
    try:
        settings = load_settings()
        dataset, digest = load_dataset(args.split)
        if not (
            args.execute
            and settings.provider == "openrouter"
            and settings.openrouter_free_only
            and not settings.allow_paid
            and settings.openrouter_data_collection == "deny"
        ):
            raise ModuleError("INVALID_INPUT")
        settings.check_execution()
        if args.output.exists():
            raise ModuleError("INVALID_INPUT")
        predictions, calls = measure(dataset, settings, args.max_calls)
        public = settings.public_configuration()
        public.pop("api_key_configured")
        run = Run(
            schema_version=1,
            mode="model_predictions",
            split=args.split,
            dataset_sha256=digest,
            metadata=Metadata(
                provider_id="openrouter",
                model_id=settings.model,
                prompt_version=PROMPT_VERSION,
                recorded_at=datetime.now(UTC),
                configuration=public,
                cost_currency="USD",
            ),
            cases=predictions,
        )
        payload = run.model_dump(mode="json")
        if contains_secret_fields(payload) or contains_key(
            payload, settings.api_key.get_secret_value()
        ):
            raise ModuleError("INVALID_PROVIDER_OUTPUT")
        # Exclusive creation preserves earlier runs; only screened, synthetic proposals are saved.
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(payload, output, ensure_ascii=False, indent=2)
        print(
            json.dumps(
                {
                    "model_calls": calls,
                    "memory_saved": False,
                    "human_review": "pending",
                    "quality_gate": "pending",
                    "failed_cases": sum(case.error_code is not None for case in predictions),
                }
            ),
            flush=True,
        )
        return 0
    except (ModuleError, OSError, ValueError, TypeError, RecursionError):
        print(json.dumps({"error": "SAFE_VERIFICATION_FAILURE"}), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Measure a configured free OpenRouter model on synthetic cases; never save memory."""

import argparse
import json
import os
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from threading import Lock

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
from scripts.formation.evaluate import Metadata, Prediction, Run, dataset_digest, load_dataset


@contextmanager
def evaluation_lease(path):
    """Prevent simultaneous CLI runs in this checkout; OS releases locks on exit/crash."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as lease:
        if lease.seek(0, os.SEEK_END) == 0:
            lease.write(b"\0")
            lease.flush()
        lease.seek(0)
        if os.name == "nt":
            import msvcrt

            acquire = partial(msvcrt.locking, lease.fileno(), msvcrt.LK_NBLCK, 1)
            release = partial(msvcrt.locking, lease.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            acquire = partial(fcntl.flock, lease.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            release = partial(fcntl.flock, lease.fileno(), fcntl.LOCK_UN)
        try:
            acquire()
        except OSError:
            raise ModuleError("CANCELLED") from None
        try:
            yield
        finally:
            lease.seek(0)
            release()


class RequestGate:
    """Share serialization, spacing and a provider-failure stop across both stages."""

    def __init__(self, interval=3.1, *, clock=time.monotonic, sleeper=time.sleep):
        self.interval = interval
        self.clock = clock
        self.sleeper = sleeper
        self.lock = Lock()
        self.last_started = None
        self.failure = None

    def wait(self):
        if self.failure is not None:
            raise ModuleError("PROVIDER_UNAVAILABLE", retryable=self.failure)
        if self.last_started is not None:
            remaining = self.interval - (self.clock() - self.last_started)
            if remaining > 0:
                self.sleeper(remaining)
        self.last_started = self.clock()


class BoundedClient(ChatClient):
    def __init__(
        self, settings, calls, max_calls, *, case_id="unbound", stage="extraction", gate=None
    ):
        super().__init__(settings)
        self.calls = calls
        self.max_calls = max_calls
        self.case_id = case_id
        self.stage = stage
        self.gate = gate if gate is not None else RequestGate()

    def complete(self, model, prompt, payload, schema):
        with self.gate.lock:
            return self._complete(model, prompt, payload, schema)

    def _complete(self, model, prompt, payload, schema):
        if len(self.calls) >= self.max_calls:
            raise ModuleError("CANCELLED")
        self.gate.wait()
        call = {
            "observation": None,
            "case_id": self.case_id,
            "stage": self.stage,
            "requested_model": model,
            "error_code": None,
            "retryable": False,
        }
        self.calls.append(call)
        started = time.monotonic()
        try:
            return super().complete(model, prompt, payload, schema)
        except ModuleError as exc:
            call["error_code"] = exc.code
            call["retryable"] = exc.retryable
            if exc.code == "PROVIDER_UNAVAILABLE":
                self.gate.failure = exc.retryable
            raise
        finally:
            call["observation"] = self.last_observation
            call["latency_ms"] = (time.monotonic() - started) * 1000


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


def measure(
    dataset,
    settings,
    max_calls,
    *,
    telemetry=None,
    case_telemetry=None,
    gate=None,
    client_factory=BoundedClient,
    provider_factory=CapturingProvider,
    verifier_factory=OnceVerifier,
    policy_options_factory=None,
):
    calls, predictions = [], []
    gate = gate if gate is not None else RequestGate()
    for case in dataset.cases:
        event = case.event.model_dump(mode="json")
        first_call = len(calls)
        provider = provider_factory(
            client_factory(
                settings, calls, max_calls, case_id=case.case_id, stage="extraction", gate=gate
            )
        )
        verifier = verifier_factory(
            client_factory(
                settings, calls, max_calls, case_id=case.case_id, stage="verification", gate=gate
            )
        )
        decisions, error = [], None
        started = time.monotonic()
        try:
            proposals = Extractor(provider, verifier).extract(event)
            policy = AdmissionPolicy(
                verifier,
                lambda event_id, event=event: event if event_id == event["event_id"] else None,
                **(
                    policy_options_factory(
                        client_factory(
                            settings,
                            calls,
                            max_calls,
                            case_id=case.case_id,
                            stage="comparison",
                            gate=gate,
                        )
                    )
                    if policy_options_factory is not None
                    else {}
                ),
            )
            decisions = [
                policy.assess(candidate, case.context.model_dump(mode="json"))
                for candidate in proposals
            ]
            if any("PROVIDER_UNAVAILABLE" in decision["reason_codes"] for decision in decisions):
                raise ModuleError("PROVIDER_UNAVAILABLE")
        except ModuleError as exc:
            error = exc.code
            decisions = []
        observed = [call["observation"] for call in calls[first_call:]]
        if case_telemetry is not None:
            case_telemetry.append(
                {
                    "case_id": case.case_id,
                    "attempted_calls": len(observed),
                    "execution": (
                        "attempted"
                        if observed
                        else "provider_stop"
                        if error == "PROVIDER_UNAVAILABLE"
                        else "call_budget"
                        if error == "CANCELLED"
                        else "local_only"
                    ),
                }
            )
            if error == "CANCELLED" and not observed and getattr(gate, "token_stopped", False):
                case_telemetry[-1].update(
                    execution="token_budget",
                    required_tokens=gate.required_tokens,
                )

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
    if telemetry is not None:
        for index, call in enumerate(calls, 1):
            observation = call["observation"]
            telemetry.append(
                {
                    "call_index": index,
                    **{key: value for key, value in call.items() if key != "observation"},
                    "observed_model": observation.model if observation else None,
                    "input_tokens": observation.input_tokens if observation else None,
                    "output_tokens": observation.output_tokens if observation else None,
                    "cost_usd": observation.cost_usd if observation else None,
                    "http_status": observation.http_status if observation else None,
                    **(
                        {"provider_error_code": observation.provider_error_code}
                        if observation
                        and getattr(observation, "provider_error_code", None) is not None
                        else {}
                    ),
                }
            )
    return predictions, len(calls)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("tuning", "holdout"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--max-calls", type=int, default=24, choices=range(1, 41))
    parser.add_argument("--request-interval", type=float, default=3.1)
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
            and 3.1 <= args.request_interval <= 60
        ):
            raise ModuleError("INVALID_INPUT")
        settings.check_execution()
        telemetry_output = args.output.with_suffix(".telemetry.json")
        if args.output.exists() or telemetry_output.exists():
            raise ModuleError("INVALID_INPUT")
        telemetry, case_telemetry = [], []
        lease_path = (
            Path(__file__).resolve().parents[2] / ".pytest_cache/formation/free-evaluation.lock"
        )
        with evaluation_lease(lease_path):
            predictions, calls = measure(
                dataset,
                settings,
                args.max_calls,
                telemetry=telemetry,
                case_telemetry=case_telemetry,
                gate=RequestGate(args.request_interval),
            )
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
        call_payload = {
            "schema_version": 1,
            "dataset_sha256": digest,
            "run_sha256": dataset_digest(run),
            "prompt_version": PROMPT_VERSION,
            "calls": telemetry,
            "cases": case_telemetry,
            "execution": {
                "concurrency": 1,
                "request_interval_seconds": args.request_interval,
                "max_calls": args.max_calls,
                "automatic_retries": 0,
                "stop_on_provider_unavailable": True,
            },
        }
        for artifact in (payload, call_payload):
            if contains_secret_fields(artifact) or contains_key(
                artifact, settings.api_key.get_secret_value()
            ):
                raise ModuleError("INVALID_PROVIDER_OUTPUT")
        # Exclusive creation preserves earlier runs; only screened, synthetic proposals are saved.
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(payload, output, ensure_ascii=False, indent=2)
        with telemetry_output.open("x", encoding="utf-8") as output:
            json.dump(call_payload, output, ensure_ascii=False, indent=2)
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

"""Replay synthetic O2 labels; no model, database, credentials, or quality measurement."""

import copy
import json
from pathlib import Path

from contextbridge.contracts import Candidate, CapturedEvent
from contextbridge.engine.errors import ModuleError
from contextbridge.formation import AdmissionPolicy
from contextbridge.formation.providers.recorded import RecordedEvidenceVerifier
from contextbridge.formation.validation import validate

DATASET = Path(__file__).resolve().parents[2] / "evaluation" / "formation" / "admission-cases.json"


def patched(template: dict, changes: dict) -> dict:
    """Objects are patched recursively; arrays/scalars replace, including explicit null."""
    result = copy.deepcopy(template)
    for key, value in changes.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = patched(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_examples() -> tuple[dict, list[dict]]:
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    templates = data["templates"]
    examples = []
    for case in data["cases"]:
        example = copy.deepcopy(case)
        for kind in ("event", "candidate", "context"):
            example[kind] = patched(templates[kind], case.get(f"{kind}_patch", {}))
        example["context"]["records"] = [
            patched(templates["record"], changes) for changes in case.get("record_patches", [])
        ]
        examples.append(example)
    return data["thresholds"], examples


class UnavailableVerifier:
    def verify(self, candidate, event):
        raise TimeoutError


def evaluate(example: dict, thresholds: dict) -> dict:
    try:
        candidate = validate(Candidate, example["candidate"]).model_dump(mode="json")
        event = validate(CapturedEvent, example["event"]).model_dump(mode="json")
        verifier = (
            UnavailableVerifier()
            if example["support"] == "unavailable"
            else RecordedEvidenceVerifier([(event, candidate, example["support"])])
        )
        policy = AdmissionPolicy(
            verifier,
            lambda event_id: (
                event
                if not example.get("missing_event") and event_id == event["event_id"]
                else None
            ),
            **thresholds,
        )
        decision = policy.assess(candidate, example["context"])
        return {key: decision[key] for key in ("outcome", "reason_codes")}
    except ModuleError as exc:
        return {"error": exc.code}


def main() -> int:
    try:
        thresholds, examples = load_examples()
        results = []
        for example in examples:
            actual = evaluate(example, thresholds)
            results.append(
                {
                    "case_id": example["id"],
                    "expected": example["expected"],
                    "actual": actual,
                    "passed": actual == example["expected"],
                }
            )
        passed = sum(result["passed"] for result in results)
        print(
            json.dumps(
                {
                    "mode": "synthetic_recorded_admission",
                    "label_status": "design_labels_pending_team_review",
                    "model_quality_measured": False,
                    "thresholds": thresholds,
                    "passed": passed,
                    "total": len(results),
                    "results": results,
                },
                indent=2,
            )
        )
        return 0 if results and passed == len(results) else 1
    except (OSError, ValueError, KeyError, TypeError):
        print(json.dumps({"error": "INVALID_INPUT"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

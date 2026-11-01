"""Run synthetic consolidation scenarios without a model, credentials or a database."""

import json
from collections import defaultdict
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from contextbridge.contracts import MemoryRecord
from contextbridge.formation import Consolidator
from contextbridge.formation.providers.consolidation import (
    RecordedConsolidationVerifier,
    RecordedGroupingProvider,
)

DATASET = (
    Path(__file__).resolve().parents[2] / "evaluation" / "formation" / "consolidation-cases.json"
)
FIXED_TIME = "2026-10-09T10:00:00+00:00"


def load_cases() -> list[dict]:
    cases = json.loads(DATASET.read_text(encoding="utf-8"))["cases"]
    for case in cases:
        records = []
        for index, spec in enumerate(case["records"]):
            identity = f"contextbridge:formation:o4-fixture:{case['id']}:{index}"
            record = {
                "memory": {
                    "id": str(uuid5(NAMESPACE_URL, f"{identity}:memory")),
                    "scope": spec.get("scope", "project"),
                    "project_id": spec.get("project_id", "synthetic-formation"),
                    "type": spec["type"],
                    "conditions": spec.get("conditions", {}),
                    "created_at": FIXED_TIME,
                    "current_version": 1,
                    "version": {
                        "id": str(uuid5(NAMESPACE_URL, f"{identity}:version")),
                        "number": 1,
                        "content": spec["content"],
                        "status": "ACTIVE",
                        "valid_from": FIXED_TIME,
                        "valid_to": None,
                        "recorded_at": FIXED_TIME,
                        "source": {
                            "kind": "user",
                            "agent": "synthetic-fixture",
                            "session": case["id"],
                            "interaction": f"message-{index}",
                            "evidence": spec.get("evidence", spec["content"]),
                        },
                    },
                },
                "claim_key": spec["claim_key"],
                "confidence": None,
                "decision_state": "clear",
            }
            records.append(MemoryRecord.model_validate(record).model_dump(mode="json"))
        case["records"] = records
    return cases


def run_case(case: dict) -> list[dict]:
    buckets = defaultdict(list)
    for record in case["records"]:
        memory = record["memory"]
        key = (memory["scope"], memory["project_id"], tuple(sorted(memory["conditions"].items())))
        buckets[key].append(record)
    grouping, verification = [], []
    for records in buckets.values():
        grouping.append((records, [[r["memory"]["version"]["id"] for r in records]]))
        verification.append((records, case["support"]))
    return Consolidator(
        RecordedGroupingProvider(grouping), RecordedConsolidationVerifier(verification)
    ).propose(case["records"])


def main():
    results = []
    for case in load_cases():
        proposals = run_case(case)
        results.append(
            {
                "case_id": case["id"],
                "expected_proposals": case["expected_proposals"],
                "actual_proposals": len(proposals),
                "passed": len(proposals) == case["expected_proposals"],
            }
        )
    print(json.dumps({"model_quality_measured": False, "results": results}, indent=2))
    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

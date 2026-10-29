"""Offline threshold sensitivity on existing design labels; never calibrates production."""

import json
from collections import Counter

from scripts.formation.check_admission import evaluate, load_examples


def sensitivity():
    defaults, examples = load_examples()
    baseline = {case["id"]: evaluate(case, defaults) for case in examples}
    rows = []
    for confidence in (0.7, defaults["min_confidence"], 0.9):
        for usefulness in (0.5, defaults["min_usefulness"], 0.7):
            thresholds = {"min_confidence": confidence, "min_usefulness": usefulness}
            results = {case["id"]: evaluate(case, thresholds) for case in examples}
            rows.append(
                {
                    "thresholds": thresholds,
                    "counts": dict(Counter(r.get("outcome", "ERROR") for r in results.values())),
                    "matches_existing_design_label": sum(
                        results[case["id"]] == case["expected"] for case in examples
                    ),
                    "changed_from_default": [
                        key for key in baseline if baseline[key] != results[key]
                    ],
                }
            )
    return {
        "mode": "offline_policy_sensitivity",
        "label_status": "design_labels_pending_team_review",
        "model_quality_measured": False,
        "production_thresholds_changed": False,
        "case_count": len(examples),
        "baseline_matches_design_labels": sum(
            baseline[case["id"]] == case["expected"] for case in examples
        ),
        "rows": rows,
    }


if __name__ == "__main__":
    print(json.dumps(sensitivity(), indent=2))

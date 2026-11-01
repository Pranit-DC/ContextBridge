"""Design-labelled recorded cases check policy behavior, never actual model quality."""

import copy
import json

import pytest

from scripts.formation.check_admission import evaluate, load_examples, main

THRESHOLDS, EXAMPLES = load_examples()


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda example: example["id"])
def test_labelled_admission_scenarios(example):
    before = copy.deepcopy(example)
    assert evaluate(example, THRESHOLDS) == example["expected"]
    assert example == before


def test_runner_reports_fixture_results_without_raw_evidence(capsys):
    assert main() == 0
    raw = capsys.readouterr().out
    report = json.loads(raw)
    assert report["mode"] == "synthetic_recorded_admission"
    assert report["model_quality_measured"] is False
    assert report["label_status"] == "design_labels_pending_team_review"
    assert report["passed"] == report["total"] == len(EXAMPLES)
    assert len({result["case_id"] for result in report["results"]}) == len(EXAMPLES)
    assert EXAMPLES[0]["candidate"]["source"]["evidence"] not in raw


def test_runner_fails_on_changed_expected_label(monkeypatch, capsys):
    from scripts.formation import check_admission

    wrong = copy.deepcopy(EXAMPLES[0])
    wrong["expected"] = {"outcome": "REJECT", "reason_codes": ["DUPLICATE"]}
    monkeypatch.setattr(check_admission, "load_examples", lambda: (THRESHOLDS, [wrong]))
    assert main() == 1
    assert json.loads(capsys.readouterr().out)["passed"] == 0

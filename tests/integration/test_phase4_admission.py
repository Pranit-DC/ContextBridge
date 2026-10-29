"""Admission checks use synthetic outputs; the existing labels remain unreviewed."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from contextbridge.models import Memory
from scripts.phase4_admission import sensitivity
from tests.integration.phase4_fakes import HostedReplay, extraction_response
from tests.integration.write_fakes import Harness


def test_existing_labels_are_not_promoted_to_quality_approval_by_sensitivity():
    report = sensitivity()
    assert report["label_status"] == "design_labels_pending_team_review"
    assert not report["model_quality_measured"] and not report["production_thresholds_changed"]
    assert report["baseline_matches_design_labels"] == report["case_count"] == 29
    default = next(
        r
        for r in report["rows"]
        if r["thresholds"] == {"min_confidence": 0.8, "min_usefulness": 0.6}
    )
    assert default["changed_from_default"] == []
    assert any(r["changed_from_default"] for r in report["rows"])
    assert all(sum(r["counts"].values()) == report["case_count"] for r in report["rows"])


@pytest.mark.integration
@pytest.mark.parametrize(
    "kind,text,support,usefulness,expected",
    [
        ("FACT", "Okay, thanks.", "supported", 0.1, "LOW_USEFULNESS"),
        ("PREFERENCE", "I prefer explicit types.", "supported", 0.9, None),
        ("LESSON", "After error E731, run repair_index.py with --dry-run.", "supported", 0.9, None),
        (
            "FACT",
            "contextbridge uses an unconfirmed replica.",
            "unsupported",
            0.9,
            "UNSUPPORTED_CLAIM",
        ),
        ("STATE", "contextbridge might be frozen.", "uncertain", 0.9, "INSUFFICIENT_EVIDENCE"),
    ],
)
def test_admission_through_hosted_assembly(
    database, monkeypatch, tmp_path, kind, text, support, usefulness, expected
):
    harness = Harness(database)
    job, candidate, _ = harness.enqueue(text, claim_key=None)
    candidate.update(type=kind, usefulness=usefulness)

    def respond(name, payload):
        value = extraction_response([candidate], name, payload)
        if name == "Checks":
            value["checks"][0]["support"] = support
        return value

    replay = HostedReplay(harness, monkeypatch, tmp_path, respond)
    result = harness.process(job, replay.providers.modules)
    if expected:
        assert not result.memory_ids and result.reason_codes == [expected]
    else:
        assert result.status == "succeeded" and len(result.memory_ids) == 1
    with Session(database[1]) as db:
        assert (db.scalar(select(Memory)) is not None) == (expected is None)
    assert replay.snapshot()["calls"] == {"groq": 2, "cloudflare": 0}

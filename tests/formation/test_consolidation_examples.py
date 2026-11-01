"""Design-labelled fixture checks; these counts are not semantic model scores."""

import pytest

from scripts.formation.demo_consolidation import load_cases, run_case


@pytest.mark.parametrize("case", load_cases(), ids=lambda case: case["id"])
def test_consolidation_scenarios(case):
    proposals = run_case(case)
    assert len(proposals) == case["expected_proposals"]
    by_id = {r["memory"]["version"]["id"]: r for r in case["records"]}
    for proposal in proposals:
        for version_id in proposal["source_version_ids"]:
            record = by_id[version_id]
            assert record["memory"]["version"]["content"] in proposal["summary"]
            assert (proposal["scope"], proposal["project_id"], proposal["conditions"]) == (
                record["memory"]["scope"],
                record["memory"]["project_id"],
                record["memory"]["conditions"],
            )

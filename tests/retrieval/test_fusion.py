from datetime import UTC, datetime

import pytest

from contextbridge.contracts import RankedMatch, RetrievalQuery
from contextbridge.retrieval.fusion import fuse, is_applicable
from tests.retrieval.fakes import make_record, match, query, version_id

NOW = datetime(2026, 10, 10, tzinfo=UTC)


def q(**overrides):
    return RetrievalQuery.model_validate(query(as_of="2026-10-10T00:00:00Z", **overrides))


def ranked(*items):
    return [RankedMatch.model_validate(m) for m in items]


def test_agreement_across_channels_beats_a_single_top_rank():
    solo, shared = make_record("solo"), make_record("shared")
    matches = ranked(
        match(solo, "lexical", 1),
        match(shared, "lexical", 2),
        match(shared, "semantic", 2),
    )
    ordered = fuse(matches, q(), NOW, rrf_k=60)
    assert [version_id(f.record.model_dump(mode="json")) for f in ordered] == [
        version_id(shared),
        version_id(solo),
    ]
    assert ordered[0].channels == ("lexical", "semantic")


def test_same_version_in_one_channel_counts_once_at_its_best_rank():
    record = make_record()
    ordered = fuse(
        ranked(match(record, "lexical", 5), match(record, "lexical", 2)), q(), NOW, rrf_k=60
    )
    assert len(ordered) == 1
    assert ordered[0].score == pytest.approx(1 / 62)


def test_equal_scores_order_is_independent_of_input_order():
    records = [make_record(f"r{i}", created_at="2026-10-09T10:00:01Z") for i in range(6)]
    forward = ranked(*(match(r, "lexical", 1) for r in records))
    ids = lambda items: [str(f.version_id) for f in fuse(items, q(), NOW, rrf_k=60)]  # noqa: E731
    assert ids(forward) == ids(list(reversed(forward)))


def test_project_memory_precedes_developer_memory_even_with_lower_rank():
    developer = make_record("dev", scope="developer")
    project = make_record("proj")
    ordered = fuse(
        ranked(match(developer, "lexical", 1), match(project, "lexical", 9)),
        q(include_developer=True),
        NOW,
        rrf_k=60,
    )
    assert [f.record.memory.scope for f in ordered] == ["project", "developer"]


@pytest.mark.parametrize(
    ("record", "overrides", "expected"),
    [
        (make_record(), {}, True),
        (make_record(project_id="other"), {}, False),
        (make_record(scope="developer"), {}, False),
        (make_record(scope="developer"), {"include_developer": True}, True),
        (make_record(scope="developer"), {"scope": "developer", "project_id": None}, True),
        (make_record(), {"scope": "developer", "project_id": None}, False),
        (make_record(conditions={"environment": "production"}), {}, False),
        (
            make_record(conditions={"environment": "production"}),
            {"conditions": {"environment": "staging"}},
            False,
        ),
        (
            make_record(conditions={"environment": "production"}),
            {"conditions": {"environment": "production", "os": "linux"}},
            True,
        ),
        (make_record(valid_from="2026-10-11T00:00:00Z"), {}, False),
        (make_record(status="SUPERSEDED", valid_to="2026-10-09T12:00:00Z"), {}, False),
        (make_record(status="SUPERSEDED", valid_to=None), {}, False),
    ],
)
def test_applicability_rules(record, overrides, expected):
    assert (
        is_applicable(
            RankedMatch.model_validate(match(record, "lexical", 1)).record, q(**overrides), NOW
        )
        is expected
    )

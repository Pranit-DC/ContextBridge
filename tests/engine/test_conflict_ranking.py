from contextbridge.contracts import RankedMatch, RetrievalQuery
from contextbridge.engine.conflict_ranking import ConflictRankingPolicy
from contextbridge.retrieval.fusion import fuse, to_card
from tests.retrieval.fakes import make_record, match, query


def baseline(records, **kwargs):
    request = RetrievalQuery.model_validate(query(**{"as_of": "2026-10-15T12:00:00Z", **kwargs}))
    matches = [
        RankedMatch.model_validate(match(record, "semantic", i + 1))
        for i, record in enumerate(records)
    ]
    return [to_card(item) for item in fuse(matches, request, request.as_of, rrf_k=60)]


def test_fusion_comparison_clear_context_then_both_unresolved_alternatives():
    records = [
        make_record("PostgreSQL", decision_state="contested"),
        make_record("Clear database port: 5432"),
        make_record("SQLite", decision_state="contested"),
    ]
    cards = baseline(records)
    edges = [(cards[0].version_id, cards[2].version_id)]
    result, warnings = ConflictRankingPolicy().rank(cards, edges, limit=3)
    assert [card.content for card in cards] == ["PostgreSQL", "Clear database port: 5432", "SQLite"]
    assert [card.content for card in result] == [
        "Clear database port: 5432",
        "PostgreSQL",
        "SQLite",
    ]
    assert [card.verification for card in result[1:]] == ["uncertain", "uncertain"]
    assert warnings == ["UNRESOLVED_CONFLICT_CONTEXT"]


def test_small_limit_marks_alternative_omission_instead_of_declaring_a_winner():
    cards = baseline(
        [
            make_record("SQLite", decision_state="contested"),
            make_record("PostgreSQL", decision_state="contested"),
        ]
    )
    result, warnings = ConflictRankingPolicy().rank(cards, [(c.version_id for c in cards)], limit=1)
    assert len(result) == 1 and result[0].verification == "uncertain"
    assert "CONFLICT_ALTERNATIVES_OMITTED" in warnings


def test_stale_similarity_and_other_conditions_cannot_reenter_eligible_pool():
    records = [
        make_record("Old PostgreSQL", status="SUPERSEDED", valid_to="2026-10-10T00:00:00Z"),
        make_record("Production SQLite", conditions={"environment": "production"}),
        make_record("Current SQLite"),
    ]
    cards = baseline(records)
    assert [card.content for card in cards] == ["Current SQLite"]
    historical = baseline(records, as_of="2026-10-09T12:00:00Z")
    assert historical[0].content == "Old PostgreSQL"


def test_policy_does_not_use_recency_confidence_or_supported_label_to_resolve_conflict():
    records = [
        make_record("A", decision_state="contested", created_at="2026-10-09T10:00:01Z"),
        make_record("B", decision_state="contested", created_at="2026-10-15T10:00:01Z"),
    ]
    records[0]["confidence"], records[1]["confidence"] = 0.1, 0.99
    cards = baseline(records)
    cards[1] = cards[1].model_copy(update={"verification": "supported"})
    result, _ = ConflictRankingPolicy().rank(cards, [], limit=2)
    assert [c.content for c in result] == ["A", "B"]
    assert all(c.verification == "uncertain" for c in result)


def test_only_small_relevance_windows_can_move_clear_context_and_project_stays_first():
    cards = baseline(
        [make_record(f"A{i}", decision_state="contested") for i in range(5)]
        + [make_record("Clear"), make_record("Global", scope="developer")],
        include_developer=True,
    )
    result, _ = ConflictRankingPolicy(window=2).rank(cards, [], limit=7)
    assert [c.content for c in result[:4]] == ["A0", "A1", "A2", "A3"]
    assert result[-1].scope == "developer"

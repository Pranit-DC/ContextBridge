import pytest

from contextbridge.contracts import MemoryRecord, RetrievalResult
from contextbridge.engine.context_budget import ContextBudget, encoded_size
from contextbridge.retrieval.fusion import Fused, to_card
from tests.retrieval.fakes import make_record


def card(content, **kwargs):
    return to_card(Fused(MemoryRecord.model_validate(make_record(content, **kwargs)), 0.1, ()))


def result(cards, warnings=None):
    return RetrievalResult(schema_version=1, cards=cards, degraded=False, warnings=warnings or [])


def test_whole_claim_omission_never_strips_late_qualifiers_or_negation():
    original = card(
        "SQLite database. " * 100 + "Only for tests; never production. 64 MB on 2026-10-14.",
        conditions={"environment": "tests"},
        decision_state="contested",
    )
    compact = ContextBudget().apply(result([original]))
    changed = compact.cards[0]
    assert "Full claim omitted" in changed.content and "SQLite" not in changed.content
    assert str(original.memory_id) in changed.content
    assert changed.conditions == original.conditions and changed.source_ref == original.source_ref
    assert changed.valid_from == original.valid_from and changed.valid_to == original.valid_to
    assert changed.decision_state == "contested" and changed.verification == original.verification
    assert "CONTEXT_CONTENT_OMITTED" in compact.warnings
    assert "Only for tests" in original.content  # Original full inspection source is untouched.


def test_total_budget_counts_metadata_unicode_and_json_escaping():
    cards = [card('漢字 "\\\n' * 110) for _ in range(20)]
    policy = ContextBudget(max_bytes=3000, per_card_bytes=2500)
    compact = policy.apply(result(cards))
    assert encoded_size(compact) <= 3000
    assert all(encoded_size(item) <= 2500 for item in compact.cards)
    assert len(compact.cards) < len(cards) and "CONTEXT_CARDS_OMITTED" in compact.warnings


def test_oversized_metadata_is_omitted_without_silently_dropping_conditions():
    original = card("Database", conditions={f"k{i}": "v" * 128 for i in range(20)})
    compact = ContextBudget(per_card_bytes=500).apply(result([original]))
    assert compact.cards == [] and "CONTEXT_CARDS_OMITTED" in compact.warnings
    assert len(original.conditions) == 20


def test_conflict_omission_and_warning_bounds_are_visible():
    compact = ContextBudget(max_bytes=2048).apply(
        result(
            [card("SQLite " * 200, decision_state="contested") for _ in range(5)],
            [f"WARNING_{i}" for i in range(20)],
        )
    )
    assert len(compact.warnings) <= 20 and encoded_size(compact) <= 2048
    assert "CONFLICT_ALTERNATIVES_OMITTED" in compact.warnings
    assert "WARNINGS_OMITTED" in compact.warnings


def test_short_and_no_match_results_are_compatible_and_unchanged():
    for original in [result([]), result([card("SQLite for tests only, effective 2026-10-14.")])]:
        assert ContextBudget().apply(original) == original


def test_bounds_are_validated():
    with pytest.raises(ValueError):
        ContextBudget(max_bytes=20)


def test_omission_marker_obeys_smallest_injected_content_bound():
    compact = ContextBudget(content_characters=128).apply(result([card("Database " * 100)]))
    assert len(compact.cards[0].content) <= 128

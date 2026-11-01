from contextbridge.engine.context_budget import ContextBudget
from tests.engine.test_context_budget import card, result


def test_budget_marks_omission_of_edge_linked_uncertain_card_without_contested_flag():
    original = card("Database", conditions={f"condition{i}": "x" * 128 for i in range(20)})
    original = original.model_copy(update={"verification": "uncertain"})
    compact = ContextBudget(per_card_bytes=500).apply(
        result([original], ["UNRESOLVED_CONFLICT_CONTEXT"])
    )
    assert compact.cards == []
    assert "CONFLICT_ALTERNATIVES_OMITTED" in compact.warnings

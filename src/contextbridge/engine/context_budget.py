"""Exact serialized-size bounds for V1 rich context, applied after stored-field validation."""

import json
from dataclasses import dataclass

from contextbridge.contracts import RetrievalResult


def encoded_size(value):
    """UTF-8 bytes in the JSON text used by MCP (including punctuation/escaping/metadata).

    This is a size bound, not a token count or estimate. HTTP's compact JSON is no larger.
    Transport/protocol envelopes and the user's other conversation context are outside it.
    """
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))


@dataclass(frozen=True)
class ContextBudget:
    max_bytes: int = 12_000
    per_card_bytes: int = 4_000
    content_characters: int = 1_500

    def __post_init__(self):
        if not (
            2_048 <= self.max_bytes <= 64_000
            and 256 <= self.per_card_bytes <= 16_000
            and 128 <= self.content_characters <= 8_000
        ):
            raise ValueError("Invalid context budget")

    def apply(self, result):
        cards, flags = [], []
        for card in result.cards:
            if (
                len(card.content) > self.content_characters
                or encoded_size(card) > self.per_card_bytes
            ):
                # A prefix could erase a later qualifier or negation. Omit the complete claim
                # instead of returning an apparently self-contained, misleading fragment.
                card = card.model_copy(
                    update={
                        "content": (
                            "[Full claim omitted for context budget; inspect memory "
                            f"{card.memory_id}, version {card.version_number}, "
                            "for complete text and evidence.]"
                        )
                    }
                )
                flags.append("CONTEXT_CONTENT_OMITTED")
            if encoded_size(card) > self.per_card_bytes:
                flags.append("CONTEXT_CARDS_OMITTED")
                if card.decision_state == "contested":
                    flags.append("CONFLICT_ALTERNATIVES_OMITTED")
                continue
            cards.append(card)

        def response():
            warnings = list(dict.fromkeys(flags + result.warnings))
            if len(warnings) > 20:
                warnings = warnings[:19] + ["WARNINGS_OMITTED"]
            return RetrievalResult(
                schema_version=1, cards=cards, degraded=result.degraded, warnings=warnings
            )

        compact = response()
        while encoded_size(compact) > self.max_bytes and cards:
            omitted = cards.pop()
            flags.append("CONTEXT_CARDS_OMITTED")
            if omitted.decision_state == "contested":
                flags.append("CONFLICT_ALTERNATIVES_OMITTED")
            compact = response()
        return compact

from types import SimpleNamespace

from contextbridge.contracts import MemoryRecord, RetrievalResult
from contextbridge.engine.retrieval_warnings import reconcile_related
from contextbridge.retrieval.fusion import Fused, to_card
from tests.retrieval.fakes import make_record


def test_disclosure_tracks_surviving_related_cards_without_changing_other_warnings():
    seed, related = [
        to_card(Fused(MemoryRecord.model_validate(make_record(text)), 0.1, ()))
        for text in ("Direct", "Related")
    ]
    repository = SimpleNamespace(
        expanded_version_ids={seed.version_id, related.version_id},
        direct_version_ids={seed.version_id},
    )
    full = RetrievalResult(
        schema_version=1,
        cards=[seed, related],
        degraded=True,
        warnings=["EMBEDDING_UNAVAILABLE", "RELATED_MEMORIES_INCLUDED"],
    )
    assert reconcile_related(full, repository) == full
    limited = reconcile_related(full.model_copy(update={"cards": [seed]}), repository)
    assert limited.cards == [seed] and limited.warnings == ["EMBEDDING_UNAVAILABLE"]
    empty = reconcile_related(full.model_copy(update={"cards": []}), repository)
    assert empty.cards == [] and empty.warnings == ["EMBEDDING_UNAVAILABLE"]

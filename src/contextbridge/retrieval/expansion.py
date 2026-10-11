"""Bounded expansion from retrieved memories to the memories they are related to.

The repository walks stored relationships; this module does not trust it. Every returned record is
checked again against the caller's scope, conditions, and time, deduplicated against everything
already seen (which also stops cycles), and confirmed live. Expansion only fills spare card slots,
so it can never push out a direct match or exceed the caller's limit.
"""

from pydantic import ValidationError

from contextbridge.contracts import MemoryRecord, RetrievalQuery
from contextbridge.contracts.interfaces import RetrievalRepository
from contextbridge.retrieval.fusion import Fused, is_applicable

MAX_HOPS = 3


def expand_related(
    seeds: list[Fused],
    repository: RetrievalRepository,
    request: RetrievalQuery,
    wire: dict,
    *,
    slots: int,
    max_hops: int,
    warnings: list[str],
) -> list[Fused]:
    """Return at most ``slots`` related, applicable, live records, nearest hop first."""
    if slots <= 0 or max_hops <= 0 or not seeds:
        return []
    visited = {str(seed.version_id) for seed in seeds}
    frontier = [str(seed.version_id) for seed in seeds]
    found: list[Fused] = []

    for _ in range(min(max_hops, MAX_HOPS)):
        remaining = slots - len(found)
        if remaining <= 0 or not frontier:
            break
        try:
            raw = repository.expand(frontier, wire, remaining)
        except Exception:
            warnings.append("EXPANSION_UNAVAILABLE")
            break
        if not isinstance(raw, list):
            warnings.append("INVALID_MATCHES_DROPPED")
            break

        fresh: list[Fused] = []
        for entry in raw:
            try:
                record = MemoryRecord.model_validate(entry)
            except (ValidationError, TypeError, ValueError):
                warnings.append("INVALID_MATCHES_DROPPED")
                continue
            version_id = str(record.memory.version.id)
            if version_id in visited:
                continue
            visited.add(version_id)  # also remembered when rejected, so it is never retried
            if is_applicable(record, request, request.as_of):
                fresh.append(Fused(record, 0.0, ("expansion",)))

        fresh.sort(key=_order)
        frontier = []
        for item in fresh:
            if len(found) >= slots:
                break
            try:
                live = repository.is_live(str(item.version_id), wire)
            except Exception:
                warnings.append("LIVENESS_UNAVAILABLE")
                continue
            if live is True:
                found.append(item)
                frontier.append(str(item.version_id))
    return found


def _order(item: Fused):
    memory = item.record.memory
    return (
        0 if memory.scope == "project" else 1,
        -memory.created_at.timestamp(),
        str(item.version_id),
    )

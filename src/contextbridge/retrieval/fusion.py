"""Pure ranking policy: applicability checks, reciprocal rank fusion, and compact cards.

Nothing here reads storage or providers. The repository is trusted to filter, but never relied
on for safety: every match is checked again against the caller's explicit filters.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from contextbridge.contracts import MemoryCard, MemoryRecord, RankedMatch, RetrievalQuery, SourceRef
from contextbridge.contracts.messages import Verification
from contextbridge.schemas import Scope

CHANNELS = ("lexical", "semantic", "symbolic")


@dataclass(frozen=True)
class Fused:
    record: MemoryRecord
    score: float
    channels: tuple[str, ...]

    @property
    def version_id(self) -> UUID:
        return self.record.memory.version.id


def is_applicable(record: MemoryRecord, query: RetrievalQuery, instant: datetime) -> bool:
    """True only if the record satisfies the caller's scope, conditions, and effective time."""
    memory, version = record.memory, record.memory.version
    if query.scope == Scope.PROJECT:
        in_project = memory.scope == Scope.PROJECT and memory.project_id == query.project_id
        shared = memory.scope == Scope.DEVELOPER and query.include_developer
        if not (in_project or shared):
            return False
    elif memory.scope != Scope.DEVELOPER:
        return False
    # Every stored condition must be satisfied; an unconditional memory always applies.
    if any(query.conditions.get(key) != value for key, value in memory.conditions.items()):
        return False
    if version.valid_from > instant or (
        version.valid_to is not None and version.valid_to <= instant
    ):
        return False
    # A closed-out version must carry its end time; a contradictory record is not trustworthy.
    return not (version.status == "SUPERSEDED" and version.valid_to is None)


def fuse(
    matches: list[RankedMatch],
    query: RetrievalQuery,
    instant: datetime,
    *,
    rrf_k: int,
) -> list[Fused]:
    """Reciprocal rank fusion over channels, deduplicated by version ID.

    Raw scores from different channels are not comparable, so only each channel's rank counts:
    a version earns 1 / (k + rank) from every channel that returned it, at its best rank there.
    Order is project-first (as the baseline search), then score, recency, and version ID, so
    equal scores always produce the same order.
    """
    best: dict[tuple[str, UUID], int] = {}
    records: dict[UUID, MemoryRecord] = {}
    for match in matches:
        if not is_applicable(match.record, query, instant):
            continue
        version_id = match.record.memory.version.id
        key = (match.channel, version_id)
        best[key] = min(best.get(key, match.rank), match.rank)
        records.setdefault(version_id, match.record)

    fused = []
    for version_id, record in records.items():
        # Fixed channel order keeps floating-point sums identical across runs.
        hits = [(c, best[(c, version_id)]) for c in CHANNELS if (c, version_id) in best]
        score = sum(1 / (rrf_k + rank) for _, rank in hits)
        fused.append(Fused(record, score, tuple(c for c, _ in hits)))

    def order(item: Fused):
        memory = item.record.memory
        project_first = 0 if memory.scope == Scope.PROJECT else 1
        return (project_first, -item.score, -memory.created_at.timestamp(), str(item.version_id))

    return sorted(fused, key=order)


def to_card(item: Fused, verification: Verification = "not_requested") -> MemoryCard:
    memory, version = item.record.memory, item.record.memory.version
    return MemoryCard(
        memory_id=memory.id,
        version_id=version.id,
        version_number=version.number,
        type=memory.type,
        content=version.content,
        scope=memory.scope,
        project_id=memory.project_id,
        conditions=memory.conditions,
        valid_from=version.valid_from,
        valid_to=version.valid_to,
        decision_state=item.record.decision_state,
        verification=verification,
        source_ref=SourceRef(
            agent=version.source.agent,
            session=version.source.session,
            interaction=version.source.interaction,
        ),
    )

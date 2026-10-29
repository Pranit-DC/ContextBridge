"""Conservative bounded reranking after fusion and authorization, never truth adjudication."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ConflictRankingPolicy:
    window: int = 4
    max_candidates: int = 20
    max_edges: int = 200

    def __post_init__(self):
        if not (
            1 <= self.window <= 5 and 1 <= self.max_candidates <= 20 and 1 <= self.max_edges <= 200
        ):
            raise ValueError("Invalid ranking bounds")

    def rank(self, cards, edges, *, limit):
        """Prefer clear context inside small relevance windows; keep disagreements together.

        A disputed card is uncertain even if a verifier called it supported. Confidence and
        recency are never used here. Fusion supplies relevance order, not truth labels.
        """
        if len(cards) > self.max_candidates or len(edges) > self.max_edges or not 1 <= limit <= 20:
            raise ValueError("Ranking input exceeds bounds")
        by_id = {card.version_id: card for card in cards}
        neighbors = {identifier: set() for identifier in by_id}
        disputed = {card.version_id for card in cards if card.decision_state == "contested"}
        missing = False
        for left, right in edges:
            disputed.update(node for node in (left, right) if node in by_id)
            if left in by_id and right in by_id and left != right:
                neighbors[left].add(right)
                neighbors[right].add(left)
            elif left in by_id or right in by_id:
                missing = True
        positions = {card.version_id: index for index, card in enumerate(cards)}
        ordered = sorted(
            cards,
            key=lambda card: (
                card.scope != "project",
                positions[card.version_id] // self.window,
                card.version_id in disputed,
                positions[card.version_id],
            ),
        )
        result, visited = [], set()
        for card in ordered:
            if card.version_id in visited:
                continue
            bundle, frontier = {card.version_id}, {card.version_id}
            while frontier:
                following = set().union(*(neighbors[node] for node in frontier)) - bundle
                bundle.update(following)
                frontier = following
            peers = sorted(
                bundle, key=lambda node: (by_id[node].scope != "project", positions[node])
            )
            for identifier in peers:
                visited.add(identifier)
                candidate = by_id[identifier]
                if identifier in disputed:
                    candidate = candidate.model_copy(update={"verification": "uncertain"})
                result.append(candidate)
        result.sort(key=lambda card: card.scope != "project")
        selected = result[:limit]
        warnings = []
        if disputed:
            warnings.append("UNRESOLVED_CONFLICT_CONTEXT")
            returned = {card.version_id for card in selected}
            if disputed - returned or missing:
                warnings.append("CONFLICT_ALTERNATIVES_OMITTED")
            if missing or any(not neighbors[node] for node in disputed):
                warnings.append("CONFLICT_ALTERNATIVES_NOT_IN_POOL")
        return selected, warnings

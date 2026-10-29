"""Keep graph disclosures consistent with the final, bounded response."""

from functools import wraps


def final_graph_disclosure(operation):
    @wraps(operation)
    def checked(service, *args, **kwargs):
        service._graph_repository = None
        result = operation(service, *args, **kwargs)
        return reconcile_related(result, service._graph_repository)

    return checked


def reconcile_related(result, repository):
    expanded = getattr(repository, "expanded_version_ids", None)
    if expanded is not None and not any(card.version_id in expanded for card in result.cards):
        return result.model_copy(
            update={"warnings": [w for w in result.warnings if w != "RELATED_MEMORIES_INCLUDED"]}
        )
    return result

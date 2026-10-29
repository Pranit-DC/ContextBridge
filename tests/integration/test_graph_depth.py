"""HTTP -> actual retriever -> PostgreSQL graph; no hosted embedding calls."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from contextbridge.models import MemoryEdge
from contextbridge.retrieval import RetrievalConfig, Retriever
from contextbridge.schemas import UpdateMemory
from contextbridge.service import MemoryService
from tests.integration.retrieval_fakes import create, query
from tests.integration.test_retrieval_api import api

pytestmark = pytest.mark.integration


def node(database, number, content=None, **changes):
    # Stable UUID order makes backtracking consume a small repository limit before forward nodes.
    with patch(
        "contextbridge.service.uuid4", side_effect=[UUID(int=2 * number), UUID(int=2 * number + 1)]
    ):
        return create(database, content=content or f"Neighbor {number}.", **changes)


def link(database, pairs):
    with Session(database[1]) as session:
        for left, right in pairs:
            session.add(
                MemoryEdge(
                    id=uuid4(),
                    from_version_id=left.version.id,
                    to_version_id=right.version.id,
                    relation="related_to",
                )
            )
        session.commit()


def retrieve(database, *, hops=3, **changes):
    retriever = Retriever(RetrievalConfig(expand_graph=True, max_hops=hops))
    with api(database, retriever) as client:
        response = client.post(
            "/v1/retrieval/search", json=query(**{"query": "graphroot", "limit": 20, **changes})
        )
    assert response.status_code == 200, response.text
    return response.json()


def ids(result):
    return [UUID(card["memory_id"]) for card in result["cards"]]


@pytest.mark.parametrize("hops", [1, 2, 3])
def test_max_hops_means_actual_edges_from_direct_matches(database, hops):
    chain = [node(database, i + 1, "graphroot" if i == 0 else None) for i in range(8)]
    link(database, zip(chain[:-1], chain[1:], strict=True))
    result = retrieve(database, hops=hops)
    assert ids(result) == [item.id for item in chain[: hops + 1]]
    assert "RELATED_MEMORIES_INCLUDED" in result["warnings"]


@pytest.mark.parametrize("limit", [1, 2, 3, 4])
def test_backtracking_cannot_starve_forward_neighbors_or_exceed_limit(database, limit):
    chain = [node(database, i + 1, "graphroot" if i == 0 else None) for i in range(5)]
    link(database, zip(chain[:-1], chain[1:], strict=True))
    result = retrieve(database, limit=limit)
    assert ids(result) == [item.id for item in chain[:limit]]
    if limit == 1:
        assert "RELATED_MEMORIES_INCLUDED" not in result["warnings"]


def test_cycles_diamonds_incoming_edges_and_multiple_seeds_are_deduplicated(database):
    a, b, c, d, e = [node(database, i, "graphroot" if i < 3 else None) for i in range(1, 6)]
    link(database, [(a, c), (c, a), (b, c), (b, d), (c, d), (d, e), (e, b)])
    result = retrieve(database)
    found = ids(result)
    assert set(found) == {a.id, b.id, c.id, d.id, e.id}
    assert len(found) == len(set(found))
    assert set(found[:2]) == {a.id, b.id}


@pytest.mark.parametrize(
    "boundary", ["owner", "project", "conditions", "time", "stale", "deleted", "developer"]
)
def test_ineligible_bridge_is_neither_returned_nor_traversed(database, boundary):
    start = datetime.now(UTC) - timedelta(days=3)
    seed = node(database, 1, "graphroot", valid_from=start.isoformat())
    changes = {
        "owner": {"owner": "other-owner"},
        "project": {"project_id": "other-project"},
        "conditions": {"conditions": {"environment": "production"}},
        "developer": {"scope": "developer", "project_id": None},
        "time": {"valid_from": (start + timedelta(days=2)).isoformat()},
    }.get(boundary, {"valid_from": start.isoformat()})
    bridge = node(database, 2, **changes)
    behind = node(database, 3, valid_from=start.isoformat())
    link(database, [(seed, bridge), (bridge, behind)])
    with Session(database[1]) as session:
        service = MemoryService(session, "developer-a")
        if boundary == "deleted":
            service.forget(bridge.id)
        elif boundary == "stale":
            service.update(
                bridge.id,
                UpdateMemory(
                    expected_version=1,
                    content="Replacement node.",
                    source=bridge.version.source,
                    valid_from=start + timedelta(days=1),
                ),
            )
    request = {"as_of": (start + timedelta(days=1)).isoformat()} if boundary == "time" else {}
    assert ids(retrieve(database, **request)) == [seed.id]


def test_explicit_condition_and_developer_opt_in_allow_only_the_requested_path(database):
    seed = node(database, 1, "graphroot")
    production = node(database, 2, conditions={"environment": "production"})
    global_node = node(database, 3, scope="developer", project_id=None)
    tail = node(database, 4)
    link(database, [(seed, production), (production, global_node), (global_node, tail)])
    assert ids(retrieve(database, conditions={"environment": "staging"})) == [seed.id]
    assert set(ids(retrieve(database, conditions={"environment": "production"}))) == {
        seed.id,
        production.id,
    }
    assert set(
        ids(retrieve(database, conditions={"environment": "production"}, include_developer=True))
    ) == {
        seed.id,
        production.id,
        global_node.id,
        tail.id,
    }


def test_supersedes_does_not_present_history_as_current_graph_truth(database):
    start = datetime.now(UTC) - timedelta(days=3)
    change = start + timedelta(days=1)
    seed = node(database, 1, "graphroot", valid_from=start.isoformat())
    old = node(database, 2, valid_from=start.isoformat())
    link(database, [(seed, old)])
    with Session(database[1]) as session:
        current = MemoryService(session, "developer-a").update(
            old.id,
            UpdateMemory(
                expected_version=1,
                content="Current replacement.",
                source=old.version.source,
                valid_from=change,
            ),
        )
    assert ids(retrieve(database)) == [seed.id]
    before = retrieve(database, as_of=(change - timedelta(microseconds=1)).isoformat())
    assert set(ids(before)) == {seed.id, old.id}
    assert next(c for c in before["cards"] if c["memory_id"] == str(old.id))["version_id"] == str(
        old.version.id
    )
    assert current.version.id != old.version.id

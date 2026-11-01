import pytest

from contextbridge.retrieval import RetrievalConfig, Retriever
from tests.retrieval.fakes import (
    FakeEmbedder,
    FakeRepository,
    make_record,
    match,
    query,
    version_id,
)


def search(repo, q=None, **config):
    config = {"expand_graph": True, **config}
    return Retriever(RetrievalConfig(**config)).search(
        q or query(limit=5), repo, FakeEmbedder(), None
    )


def ids(result):
    return [card["version_id"] for card in result["cards"]]


def seeded(*direct):
    return FakeRepository(lexical=[match(r, "lexical", i) for i, r in enumerate(direct, 1)])


def test_related_memory_fills_a_spare_slot_after_direct_matches_and_is_disclosed():
    seed, related = make_record("current decision"), make_record("earlier decision")
    repo = seeded(seed)
    repo.graph = {version_id(seed): [related]}
    result = search(repo)
    assert ids(result) == [version_id(seed), version_id(related)]
    assert "RELATED_MEMORIES_INCLUDED" in result["warnings"]
    assert result["degraded"] is False


def test_expansion_is_off_by_default():
    seed, related = make_record("a"), make_record("b")
    repo = seeded(seed)
    repo.graph = {version_id(seed): [related]}
    result = Retriever().search(query(limit=5), repo, FakeEmbedder(), None)
    assert ids(result) == [version_id(seed)]
    assert repo.expand_calls == []


def test_expansion_never_exceeds_the_callers_limit_or_displaces_direct_matches():
    seeds = [make_record(f"s{i}") for i in range(2)]
    extras = [make_record(f"x{i}") for i in range(5)]
    repo = seeded(*seeds)
    repo.graph = {version_id(seeds[0]): extras}
    result = search(repo, query(limit=3))
    assert len(result["cards"]) == 3
    assert ids(result)[:2] == [version_id(s) for s in seeds]
    assert repo.expand_calls[0][2] == 1  # the repository is told only the spare slots


def test_no_expansion_when_direct_matches_already_fill_the_limit():
    seeds = [make_record(f"s{i}") for i in range(3)]
    repo = seeded(*seeds)
    repo.graph = {version_id(seeds[0]): [make_record("x")]}
    search(repo, query(limit=3))
    assert repo.expand_calls == []


def test_no_expansion_without_a_direct_match_to_start_from():
    repo = seeded()
    repo.graph = {"anything": [make_record("x")]}
    result = search(repo)
    assert repo.expand_calls == []
    assert result["cards"] == [] and "NO_RESULTS" in result["warnings"]


def test_a_cycle_terminates_and_never_repeats_a_card():
    a, b = make_record("a"), make_record("b")
    repo = seeded(a)
    repo.graph = {version_id(a): [b], version_id(b): [a]}
    result = search(repo, max_hops=3)
    assert ids(result) == [version_id(a), version_id(b)]
    assert len(repo.expand_calls) <= 3


def test_hops_are_bounded():
    chain = [make_record(f"n{i}") for i in range(6)]
    repo = seeded(chain[0])
    repo.graph = {version_id(chain[i]): [chain[i + 1]] for i in range(5)}
    one = search(repo, max_hops=1)
    assert ids(one) == [version_id(c) for c in chain[:2]]
    repo.expand_calls.clear()
    three = search(repo, max_hops=3)
    assert ids(three) == [version_id(c) for c in chain[:4]]
    assert len(repo.expand_calls) == 3


def test_every_hop_is_filtered_and_unrelated_records_do_not_extend_the_walk():
    seed = make_record("seed")
    other_project = make_record("leak", project_id="other")
    behind_leak = make_record("beyond the leak")
    production_only = make_record("prod", conditions={"environment": "production"})
    ok = make_record("ok")
    repo = seeded(seed)
    repo.graph = {
        version_id(seed): [other_project, production_only, ok],
        version_id(other_project): [behind_leak],
    }
    result = search(repo, max_hops=3)
    assert ids(result) == [version_id(seed), version_id(ok)]
    for frontier, _, _ in repo.expand_calls:
        assert version_id(other_project) not in frontier


def test_historical_query_only_follows_to_versions_valid_then():
    seed = make_record("seed")
    later = make_record("created after the query time", valid_from="2026-10-20T00:00:00Z")
    repo = seeded(seed)
    repo.graph = {version_id(seed): [later]}
    assert ids(search(repo, query(limit=5, as_of="2026-10-10T00:00:00Z"))) == [version_id(seed)]


def test_deleted_related_records_are_dropped_and_do_not_extend_the_walk():
    seed, deleted, beyond = make_record("seed"), make_record("deleted"), make_record("beyond")
    repo = seeded(seed)
    repo.graph = {version_id(seed): [deleted], version_id(deleted): [beyond]}
    repo.live = {version_id(seed), version_id(beyond)}
    result = search(repo, max_hops=3)
    assert ids(result) == [version_id(seed)]


def test_unconfirmed_liveness_of_a_related_record_fails_closed():
    seed, related = make_record("seed"), make_record("related")
    repo = seeded(seed)
    repo.graph = {version_id(seed): [related]}
    original = repo.is_live
    repo.is_live = lambda vid, q: (
        (_ for _ in ()).throw(RuntimeError("down"))
        if vid == version_id(related)
        else original(vid, q)
    )
    result = search(repo)
    assert ids(result) == [version_id(seed)]
    assert "LIVENESS_UNAVAILABLE" in result["warnings"] and result["degraded"] is True


def test_expansion_failure_keeps_direct_results_and_degrades_visibly():
    seed = make_record("seed")
    repo = seeded(seed)
    repo.failing["expand"] = RuntimeError("graph offline")
    result = search(repo)
    assert ids(result) == [version_id(seed)]
    assert result["degraded"] is True and "EXPANSION_UNAVAILABLE" in result["warnings"]


@pytest.mark.parametrize("bad", ["not a list", [{"record": "garbage"}], [None]])
def test_malformed_repository_output_is_dropped_visibly(bad):
    seed = make_record("seed")
    repo = seeded(seed)
    repo.graph = bad
    result = search(repo)
    assert ids(result) == [version_id(seed)]
    assert "INVALID_MATCHES_DROPPED" in result["warnings"]


def test_a_related_record_equal_to_a_direct_match_is_not_duplicated():
    seed = make_record("seed")
    repo = seeded(seed)
    repo.graph = {version_id(seed): [seed]}
    result = search(repo)
    assert ids(result) == [version_id(seed)]
    assert "RELATED_MEMORIES_INCLUDED" not in result["warnings"]


def test_related_order_is_deterministic_regardless_of_repository_order():
    seed = make_record("seed")
    related = [make_record(f"r{i}") for i in range(4)]
    forward, backward = seeded(seed), seeded(seed)
    forward.graph = {version_id(seed): related}
    backward.graph = {version_id(seed): list(reversed(related))}
    assert ids(search(forward)) == ids(search(backward))


@pytest.mark.parametrize("bad", [{"max_hops": 0}, {"max_hops": 4}])
def test_invalid_hop_configuration_is_rejected(bad):
    with pytest.raises(ValueError):
        RetrievalConfig(**bad)

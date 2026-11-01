import json

import pytest

from contextbridge.contracts import RetrievalResult
from contextbridge.engine.errors import ModuleError
from contextbridge.retrieval import RetrievalConfig, Retriever, normalize_query
from tests.retrieval.fakes import (
    FIXTURES,
    FakeEmbedder,
    FakeRepository,
    FakeVerifier,
    make_record,
    match,
    query,
    snapshot,
    version_id,
)


def search(repo, q=None, embedder=None, **config):
    return Retriever(RetrievalConfig(**config)).search(
        q or query(), repo, embedder or FakeEmbedder(), FakeVerifier()
    )


def ids(result):
    return [card["version_id"] for card in result["cards"]]


def test_snapshot_produces_the_agreed_result_shape():
    snap = snapshot()
    repo = FakeRepository(
        **{
            channel: [match(snap["records"][0], channel, m["rank"]) for m in matches]
            for channel, matches in snap["channel_matches"].items()
        }
    )
    result = search(repo, snap["query"])
    expected = json.loads((FIXTURES / "retrieval-result.json").read_text(encoding="utf-8"))
    assert result == expected
    RetrievalResult.model_validate(result)


def test_version_found_by_every_channel_yields_one_card():
    record = make_record()
    repo = FakeRepository(
        lexical=[match(record, "lexical", 1)],
        semantic=[match(record, "semantic", 1)],
        symbolic=[match(record, "symbolic", 1)],
    )
    assert ids(search(repo)) == [version_id(record)]


def test_out_of_scope_records_from_a_leaky_repository_never_appear():
    good = make_record("good")
    leaks = [
        make_record("other project", project_id="other"),
        make_record("developer memory", scope="developer"),
        make_record("production only", conditions={"environment": "production"}),
        make_record("future", valid_from="2099-01-01T00:00:00Z"),
        make_record("closed", status="SUPERSEDED", valid_to="2026-10-09T10:30:00Z"),
    ]
    repo = FakeRepository(lexical=[match(r, "lexical", i) for i, r in enumerate([*leaks, good], 1)])
    assert ids(search(repo)) == [version_id(good)]


def test_historical_query_returns_the_version_valid_then_not_the_current_one():
    old = make_record(
        "uses PostgreSQL",
        status="SUPERSEDED",
        valid_from="2026-10-01T00:00:00Z",
        valid_to="2026-10-05T00:00:00Z",
        memory_id="33333333-3333-4333-8333-333333333333",
    )
    new = make_record(
        "uses SQLite",
        valid_from="2026-10-05T00:00:00Z",
        memory_id="33333333-3333-4333-8333-333333333333",
        number=2,
    )
    repo = FakeRepository(lexical=[match(new, "lexical", 1), match(old, "lexical", 2)])
    assert ids(search(repo, query(as_of="2026-10-03T00:00:00Z"))) == [version_id(old)]
    assert ids(search(repo, query(as_of="2026-10-06T00:00:00Z"))) == [version_id(new)]


def test_contested_state_stays_visible_on_the_card():
    record = make_record(decision_state="contested")
    repo = FakeRepository(lexical=[match(record, "lexical", 1)])
    assert search(repo)["cards"][0]["decision_state"] == "contested"


def test_cards_never_exceed_the_callers_limit():
    records = [make_record(f"r{i}") for i in range(8)]
    repo = FakeRepository(lexical=[match(r, "lexical", i) for i, r in enumerate(records, 1)])
    assert len(search(repo, query(limit=2))["cards"]) == 2
    assert len(search(repo, query())["cards"]) == 3
    assert len(search(repo, query(limit=20))["cards"]) == 8


def test_order_is_stable_when_scores_tie():
    records = [make_record(f"r{i}") for i in range(5)]
    forward = FakeRepository(lexical=[match(r, "lexical", 1) for r in records])
    backward = FakeRepository(lexical=[match(r, "lexical", 1) for r in reversed(records)])
    q = query(limit=5)
    assert ids(search(forward, q)) == ids(search(backward, q))


def test_embedding_provider_failure_degrades_without_claiming_semantic_search():
    record = make_record()
    repo = FakeRepository(lexical=[match(record, "lexical", 1)])
    result = search(repo, embedder=FakeEmbedder(error=TimeoutError("provider detail")))
    assert ids(result) == [version_id(record)]
    assert result["degraded"] is True
    assert "EMBEDDING_UNAVAILABLE" in result["warnings"]
    assert [call[0] for call in repo.calls] == ["lexical", "symbolic"]


@pytest.mark.parametrize(
    "embedder",
    [
        FakeEmbedder(vectors=[]),
        FakeEmbedder(vectors=[[0.1, 0.2], [0.3, 0.4]]),
        FakeEmbedder(vectors=[[0.1]], dimensions=2),
        FakeEmbedder(vectors=[[float("nan"), 0.1]]),
    ],
)
def test_invalid_embedding_output_is_treated_as_unavailable(embedder):
    repo = FakeRepository(lexical=[match(make_record(), "lexical", 1)])
    result = search(repo, embedder=embedder)
    assert result["degraded"] is True
    assert all(call[0] != "semantic" for call in repo.calls)


def test_semantic_channel_receives_labelled_vector_and_bounded_limit():
    repo = FakeRepository()
    search(repo, embedder=FakeEmbedder(model_id="m1", dimensions=2), channel_limit=7)
    semantic = next(call for call in repo.calls if call[0] == "semantic")
    assert semantic[2] == {"model_id": "m1", "dimensions": 2, "vector": [0.1, 0.2]}
    assert {call[3] for call in repo.calls} == {7}
    assert all(call[2] is None for call in repo.calls if call[0] != "semantic")


def test_repository_returning_more_than_the_channel_limit_is_truncated():
    records = [make_record(f"r{i}") for i in range(10)]
    repo = FakeRepository(lexical=[match(r, "lexical", i) for i, r in enumerate(records, 1)])
    result = search(repo, query(limit=20), channel_limit=4)
    assert len(result["cards"]) == 4


def test_lexical_failure_is_a_retryable_safe_error():
    repo = FakeRepository()
    repo.failing["lexical"] = RuntimeError("password=hunter2 in SQL text")
    with pytest.raises(ModuleError) as raised:
        search(repo)
    assert (raised.value.code, raised.value.retryable) == ("STORAGE_UNAVAILABLE", True)
    assert "hunter2" not in str(raised.value)


def test_semantic_or_symbolic_failure_degrades_but_keeps_lexical_results():
    record = make_record()
    repo = FakeRepository(lexical=[match(record, "lexical", 1)])
    repo.failing["semantic"] = RuntimeError("index offline")
    repo.failing["symbolic"] = RuntimeError("index offline")
    result = search(repo)
    assert ids(result) == [version_id(record)]
    assert result["degraded"] is True
    assert {"SEMANTIC_UNAVAILABLE", "SYMBOLIC_UNAVAILABLE"} <= set(result["warnings"])


def test_records_no_longer_live_are_dropped_and_the_next_candidate_fills_the_slot():
    stale, fresh = make_record("deleted"), make_record("alive")
    repo = FakeRepository(lexical=[match(stale, "lexical", 1), match(fresh, "lexical", 2)])
    repo.live = {version_id(fresh)}
    assert ids(search(repo, query(limit=1))) == [version_id(fresh)]


def test_unverifiable_liveness_fails_closed():
    repo = FakeRepository(lexical=[match(make_record(), "lexical", 1)])
    repo.failing["liveness"] = RuntimeError("db down")
    result = search(repo)
    assert result["cards"] == []
    assert result["degraded"] is True
    assert "LIVENESS_UNAVAILABLE" in result["warnings"]


def test_empty_result_is_explicit_and_not_degraded():
    result = search(FakeRepository())
    assert result["cards"] == []
    assert result["warnings"] == ["NO_RESULTS"]
    assert result["degraded"] is False


def test_malformed_or_mislabelled_matches_are_dropped_visibly():
    good = make_record()
    repo = FakeRepository(
        lexical=[
            {"record": "garbage", "channel": "lexical", "rank": 1},
            match(make_record("wrong channel"), "semantic", 2),
            match(good, "lexical", 3),
        ]
    )
    result = search(repo)
    assert ids(result) == [version_id(good)]
    assert "INVALID_MATCHES_DROPPED" in result["warnings"]


def test_non_list_repository_output_returns_no_cards():
    repo = FakeRepository(lexical="not a list")
    assert search(repo)["cards"] == []


def test_explicit_filters_reach_every_channel_unchanged():
    repo = FakeRepository()
    q = query(
        query="  find   src/app_core.py::load_config()  ",
        conditions={"environment": "production"},
        include_developer=True,
        limit=5,
        as_of="2026-10-09T11:00:00Z",
    )
    search(repo, q)
    for _, sent, _, _ in repo.calls:
        assert sent["query"] == "find src/app_core.py::load_config()"
        assert sent["conditions"] == {"environment": "production"}
        assert (sent["scope"], sent["project_id"]) == ("project", "contextbridge")
        assert (sent["include_developer"], sent["limit"]) == (True, 5)
        assert sent["as_of"] == "2026-10-09T11:00:00Z"


def test_missing_as_of_is_resolved_once_for_all_stages():
    repo = FakeRepository(lexical=[match(make_record(), "lexical", 1)])
    search(repo, query(as_of=None))
    sent = {call[1]["as_of"] for call in repo.calls}
    assert len(sent) == 1
    assert None not in sent


def test_the_query_text_is_embedded_once_and_not_guessed_at():
    embedder = FakeEmbedder()
    search(FakeRepository(), query(query="which database?"), embedder)
    assert embedder.texts == [["which database?"]]


def test_secret_in_query_is_rejected_before_any_provider_call():
    embedder, repo = FakeEmbedder(), FakeRepository()
    secret = "sk-abcdefghijklmnopqrstuvwxyz"
    with pytest.raises(ModuleError) as raised:
        search(repo, query(query=f"what is {secret}"), embedder)
    assert raised.value.code == "INVALID_INPUT"
    assert secret not in str(raised.value) and secret not in repr(raised.value.args)
    assert embedder.texts == [] and repo.calls == []


@pytest.mark.parametrize(
    "bad",
    [
        {"limit": 21},
        {"limit": 0},
        {"schema_version": 2},
        {"scope": "project", "project_id": None},
        {"as_of": "2026-10-09T11:00:00"},
        {"query": "   "},
        {"unexpected": 1},
    ],
)
def test_invalid_queries_fail_safely(bad):
    with pytest.raises(ModuleError) as raised:
        normalize_query(query(**bad))
    assert raised.value.code == "INVALID_INPUT"


def test_non_dict_query_fails_safely():
    with pytest.raises(ModuleError):
        normalize_query(None)


@pytest.mark.parametrize("bad", [{"rrf_k": 0}, {"channel_limit": 0}, {"channel_limit": 101}])
def test_invalid_config_is_rejected(bad):
    with pytest.raises(ValueError):
        RetrievalConfig(**bad)


@pytest.mark.parametrize(
    "embedder",
    [
        FakeEmbedder(model_id="other-model", dimensions=2),
        FakeEmbedder(model_id="expected", dimensions=3, vectors=[[0.1, 0.2, 0.3]]),
    ],
)
def test_embedding_from_an_unexpected_model_or_size_is_never_used(embedder):
    record = make_record()
    repo = FakeRepository(lexical=[match(record, "lexical", 1)])
    result = search(repo, embedder=embedder, embedding_model_id="expected", embedding_dimensions=2)
    assert ids(result) == [version_id(record)]
    assert result["degraded"] is True and "EMBEDDING_UNAVAILABLE" in result["warnings"]
    assert all(call[0] != "semantic" for call in repo.calls)


def test_the_expected_model_is_used_when_it_matches():
    repo = FakeRepository()
    search(repo, embedder=FakeEmbedder(model_id="expected"), embedding_model_id="expected")
    assert any(call[0] == "semantic" for call in repo.calls)


def test_a_provider_timeout_degrades_to_the_other_channels_without_hanging():
    import time

    from contextbridge.retrieval.embedding import GuardedEmbeddingProvider
    from tests.retrieval.test_embedding import Backend

    record = make_record()
    repo = FakeRepository(lexical=[match(record, "lexical", 1)])
    slow = GuardedEmbeddingProvider(
        Backend(delay=1.0), model_id="m1", dimensions=2, timeout_seconds=0.05
    )
    started = time.monotonic()
    result = search(repo, embedder=slow)
    assert time.monotonic() - started < 0.5
    assert ids(result) == [version_id(record)]
    assert result["degraded"] is True and "EMBEDDING_UNAVAILABLE" in result["warnings"]
    assert all(call[0] != "semantic" for call in repo.calls)

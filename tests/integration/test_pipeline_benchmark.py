"""Real-store benchmark behavior, failure cleanup and refusal of existing content."""

import json

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from contextbridge.models import EmbeddingModel, Memory, ReindexJob, WorkItem
from scripts.benchmark_memory_pipeline import CASES, Vectors, evaluate
from tests.integration.retrieval_fakes import create
from tests.integration.test_repository import vector_database as vector_database

pytestmark = pytest.mark.integration


def empty(database):
    with Session(database[1]) as session:
        for model in (Memory, EmbeddingModel, ReindexJob, WorkItem):
            assert session.scalar(select(func.count()).select_from(model)) == 0


def test_all_modes_use_real_pgvector_keep_conflicts_and_omissions_and_clean_up(
    vector_database, monkeypatch
):
    database = vector_database

    def no_http(*args, **kwargs):
        raise AssertionError("Offline benchmark must not call hosted services")

    monkeypatch.setattr(httpx.Client, "send", no_http)
    dataset = json.loads(CASES.read_text(encoding="utf-8"))
    report = evaluate(database[0], dataset, repeats=1, scale=2)
    assert len(report["rows"]) == (len(dataset["cases"]) + 2) * 5
    assert report["all_design_checks_pass"] is True
    assert report["hosted_requests"] == 0
    assert report["model_quality_measured"] is report["independent_review_complete"] is False
    rows = {(r["case"], r["mode"]): r for r in report["rows"]}
    assert rows["paraphrase", "keyword"]["returned"] == []
    assert rows["paraphrase", "semantic"]["returned"] == ["db"]
    assert rows["stale_embedding", "semantic"]["returned"] == []
    assert rows["stale_embedding", "hybrid_compact"]["returned"] == ["db"]
    fused, ranked = (
        rows["unresolved_alternatives", name]["returned"]
        for name in ["hybrid_fusion", "hybrid_ranked"]
    )
    assert ranked[0] == "port" and fused[0] != "port"
    assert set(ranked) == set(fused)
    assert rows["long_qualified_claim", "hybrid_compact"]["full_claim_cards"] == 0
    assert (
        rows["long_qualified_claim", "hybrid_compact"]["response_bytes"]
        < rows["long_qualified_claim", "hybrid_ranked"]["response_bytes"]
    )
    assert all(
        r["query_embedding_calls_per_execution"] == (r["mode"] != "keyword") for r in report["rows"]
    )
    capacity = rows["total_context_capacity", "hybrid_compact"]
    assert 0 < len(capacity["returned"]) < 8
    assert "CONTEXT_CARDS_OMITTED" in capacity["warnings"]
    assert capacity["response_bytes"] <= 12_000
    empty(database)


def test_benchmark_refuses_existing_content_and_preserves_it(database):
    saved = create(database)
    with pytest.raises(ValueError, match="empty test store"):
        evaluate(database[0], json.loads(CASES.read_text(encoding="utf-8")))
    with Session(database[1]) as session:
        assert session.get(Memory, saved.id) is not None
        assert session.scalar(select(func.count()).select_from(Memory)) == 1


def test_benchmark_cleans_created_memory_jobs_and_vectors_after_index_failure(
    vector_database, monkeypatch
):
    database = vector_database

    def unavailable(*args):
        raise ValueError("synthetic embedding unavailable")

    monkeypatch.setattr(Vectors, "embed", unavailable)
    with pytest.raises(ValueError, match="Synthetic indexing failed"):
        evaluate(database[0], json.loads(CASES.read_text(encoding="utf-8")))
    empty(database)

"""Offline real-pgvector pipeline comparison; synthetic vectors are not model-quality evidence."""

import argparse
import hashlib
import json
import math
import os
import platform
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import median
from time import perf_counter
from uuid import uuid4

from sqlalchemy import create_engine, delete, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from contextbridge.config import Settings
from contextbridge.contracts import RetrievalQuery
from contextbridge.engine.context_budget import ContextBudget, encoded_size
from contextbridge.engine.errors import ModuleError
from contextbridge.engine.indexing import IndexService
from contextbridge.engine.modules import ModuleGateway
from contextbridge.engine.retrieval import RetrievalService
from contextbridge.models import (
    CaptureEvent,
    ConsolidationJob,
    EmbeddingModel,
    Memory,
    MemoryEdge,
    MemoryVersion,
    ReindexJob,
    WorkItem,
)
from contextbridge.retrieval import RetrievalConfig, Retriever
from contextbridge.schemas import CreateMemory, UpdateMemory
from contextbridge.service import MemoryService, MemoryServiceError

CASES = Path(__file__).resolve().parents[1] / "evaluation/pipeline-benchmarks/cases.json"
MODEL = "synthetic-benchmark-4d"
MODES = ("keyword", "semantic", "hybrid_fusion", "hybrid_ranked", "hybrid_compact")


class Vectors:
    """Explicit fixture lookup, never infer meanings or access provider credentials."""

    def __init__(self, values):
        self.values, self.calls = values, 0

    def embed(self, texts):
        self.calls += 1
        return {"model_id": MODEL, "dimensions": 4, "vectors": [self.values[t] for t in texts]}


class Channels:
    def __init__(self, repository, channels):
        self.repository, self.channels = repository, channels

    def __getattr__(self, name):
        return getattr(self.repository, name)

    def search_channel(self, channel, *args):
        return self.repository.search_channel(channel, *args) if channel in self.channels else []


class ChannelRetriever:
    def __init__(self, mode):
        self.mode = mode
        self.retriever = Retriever(
            RetrievalConfig(embedding_model_id=MODEL, embedding_dimensions=4, expand_graph=False)
        )

    def search(self, query, repository, embedder, verifier):
        channels = (
            {"lexical", "symbolic"}
            if self.mode == "keyword"
            else {"semantic"}
            if self.mode == "semantic"
            else {"lexical", "symbolic", "semantic"}
        )
        # Keyword uses no embedder: its unavailable-embedding warning is retained honestly.
        return self.retriever.search(
            query,
            Channels(repository, channels),
            None if self.mode == "keyword" else embedder,
            None,
        )


class FusionOnly:
    max_candidates, max_edges = 20, 200

    def rank(self, cards, edges, *, limit):
        return cards[:limit], []


class UnboundedContext:
    def apply(self, result):
        return result


def metrics(returned, relevant):
    if len(returned) != len(set(returned)):
        raise ValueError("Duplicate result labels invalidate benchmark metrics")
    relevant = set(relevant)
    hits = sum(label in relevant for label in returned)
    return {
        "precision_at_returned": hits / len(returned) if returned else None,
        "recall_at_limit": hits / len(relevant) if relevant else None,
        "reciprocal_rank": next(
            (1 / rank for rank, label in enumerate(returned, 1) if label in relevant),
            0.0 if relevant else None,
        ),
        "correct_abstention": not returned if not relevant else None,
    }


def percentiles(samples):
    ordered = sorted(samples)
    return {
        "samples": len(samples),
        "p50_ms": round(median(ordered), 3),
        "p95_ms": round(ordered[math.ceil(len(ordered) * 0.95) - 1], 3),
    }


def summarize(rows):
    """Macro averages exclude undefined cases and disclose their denominators."""
    output = []
    for partition, mode in sorted({(r["partition"], r["mode"]) for r in rows}):
        group = [r for r in rows if (r["partition"], r["mode"]) == (partition, mode)]
        item = {"partition": partition, "mode": mode, "cases": len(group)}
        for name in (
            "precision_at_returned",
            "recall_at_limit",
            "reciprocal_rank",
            "correct_abstention",
        ):
            values = [r[name] for r in group if r[name] is not None]
            item[name] = {
                "mean": sum(values) / len(values) if values else None,
                "defined_cases": len(values),
            }
        item["latency"] = percentiles([v for r in group for v in r["elapsed_ms"]])
        item["mean_response_bytes"] = sum(r["response_bytes"] for r in group) / len(group)
        output.append(item)
    return output


def seed(session, owner, project, case, vectors, created):
    labels, versions, content = {}, {}, {}
    start = datetime.now(UTC) - timedelta(days=2)

    def index(memory, version, value, actual_owner, actual_project, conditions, topic):
        provider = Vectors({value: vectors[topic]})
        query = RetrievalQuery(
            schema_version=1,
            scope="project",
            project_id=actual_project,
            query="benchmark",
            conditions=conditions,
        )
        service = IndexService(session, actual_owner)
        job = service.enqueue(
            query.model_dump(mode="json"), [str(version.id)], MODEL, 4, str(uuid4())
        )
        if service.process(job, provider)["status"] != "succeeded":
            raise ValueError("Synthetic indexing failed")

    for record in case["records"]:
        actual_owner = owner + "-foreign" if record.get("foreign_owner") else owner
        actual_project = record.get("project", project)
        value = record["text"] * record.get("repeat", 1) + record.get("suffix", "")
        conditions = record.get("conditions", {})
        source = {
            "kind": "user",
            "agent": "synthetic-benchmark",
            "session": case["id"],
            "interaction": record["id"],
            "evidence": value,
        }
        memory = MemoryService(session, actual_owner).create(
            CreateMemory(
                request_id=uuid4(),
                scope="project",
                project_id=actual_project,
                type="FACT",
                content=value,
                source=source,
                conditions=conditions,
                valid_from=start,
            )
        )
        created.append((actual_owner, memory.id))
        labels[memory.id], content[memory.id] = record["id"], value
        # Each record's semantic topic is an authored fixture, not a model judgment.
        if not record.get("omit_index"):
            index(
                memory,
                memory.version,
                value,
                actual_owner,
                actual_project,
                conditions,
                record["topic"],
            )
        if record.get("replacement"):
            value = record["replacement"]
            source = {**source, "evidence": value}
            memory = MemoryService(session, actual_owner).update(
                memory.id,
                UpdateMemory(
                    expected_version=1,
                    content=value,
                    source=source,
                    valid_from=start + timedelta(days=1),
                ),
            )
            content[memory.id] = value if not case.get("historical") else record["text"]
            if not record.get("skip_reindex"):
                index(
                    memory,
                    memory.version,
                    value,
                    actual_owner,
                    actual_project,
                    conditions,
                    record["topic"],
                )
        versions[record["id"]] = memory.version.id
        if record.get("contested"):
            session.get(MemoryVersion, memory.version.id).decision_state = "contested"
            session.commit()
        if record.get("forget"):
            MemoryService(session, actual_owner).forget(memory.id)
    if case.get("conflict"):
        left, right = case["conflict"]
        session.add(
            MemoryEdge(
                id=uuid4(),
                from_version_id=versions[left],
                to_version_id=versions[right],
                relation="contradicts",
            )
        )
        session.commit()
    return labels, content, start + timedelta(hours=12) if case.get("historical") else None


def evaluate(url, dataset, *, repeats=3, scale=0):
    """Use an empty migrated test DB, clean only this run's synthetic rows even on failure."""
    parsed = make_url(url)
    if parsed.get_backend_name() != "postgresql" or not (parsed.database or "").endswith("_test"):
        raise ValueError("A dedicated PostgreSQL test database is required")
    if not 1 <= repeats <= 20 or not 0 <= scale <= 2000:
        raise ValueError("Benchmark bounds exceeded")
    if dataset.get("schema_version") != 1 or not dataset.get("cases"):
        raise ValueError("Invalid benchmark dataset")
    owner, created, rows = "bench-" + uuid4().hex, [], []
    engine = create_engine(url)
    try:
        with Session(engine, expire_on_commit=False) as session:
            for model in (
                Memory,
                CaptureEvent,
                ConsolidationJob,
                ReindexJob,
                WorkItem,
                EmbeddingModel,
            ):
                if session.scalar(select(func.count()).select_from(model)):
                    raise ValueError("Benchmark requires an empty test store")
            if not session.scalar(
                text("SELECT EXISTS (SELECT FROM pg_extension WHERE extname='vector')")
            ):
                raise ValueError("Benchmark requires pgvector")
            postgres = session.scalar(text("SHOW server_version"))
            session.commit()
            settings = Settings(
                _env_file=None,
                database_url=url,
                api_token="synthetic-benchmark-access-token-only",
                developer_id=owner,
                formation_enabled=False,
                consolidation_enabled=False,
                embedding_provider=None,
            )
            cases = list(dataset["cases"])
            for size in sorted({0, min(100, scale), scale}) if scale else []:
                cases.append(
                    {
                        "id": f"scale_{size}",
                        "partition": "scale_probe",
                        "query": "benchmarkneedle",
                        "topic": "database",
                        "relevant": ["target"],
                        "records": [
                            {
                                "id": "target",
                                "text": "Database benchmarkneedle.",
                                "topic": "database",
                            }
                        ]
                        + [
                            {
                                "id": f"noise-{i}",
                                "text": f"Runtime distractor {i}.",
                                "topic": "runtime",
                            }
                            for i in range(size)
                        ],
                    }
                )
            for case in cases:
                # A fresh project per case prevents cross-case relevance contamination.
                project = "benchmark-" + case["id"]
                labels, contents, as_of = seed(
                    session, owner, project, case, dataset["vectors"], created
                )
                query = RetrievalQuery(
                    schema_version=1,
                    scope="project",
                    project_id=project,
                    query=case["query"],
                    conditions=case.get("conditions", {}),
                    limit=case.get("limit", 3),
                    as_of=as_of,
                )
                for mode in MODES:
                    embedder = Vectors({case["query"]: dataset["vectors"][case["topic"]]})
                    samples = []
                    result = None
                    first_result = None
                    stable = True
                    for iteration in range(repeats + 1):
                        before = perf_counter()
                        result = RetrievalService(
                            session,
                            settings,
                            ModuleGateway(retriever=ChannelRetriever(mode)),
                            embedder,
                            ranking_policy=FusionOnly() if mode in MODES[:3] else None,
                            context_budget=None if mode == "hybrid_compact" else UnboundedContext(),
                        ).search(query)
                        if iteration:
                            samples.append((perf_counter() - before) * 1000)
                        snapshot = result.model_dump(mode="json")
                        if first_result is None:
                            first_result = snapshot
                        stable = stable and snapshot == first_result
                    returned = [labels[c.memory_id] for c in result.cards]
                    compact = mode == "hybrid_compact"
                    omitted = "CONTEXT_CONTENT_OMITTED" in result.warnings
                    checks = {
                        "no_forbidden_results": not (
                            set(returned) & set(case.get("forbidden", []))
                        ),
                        "version_correct": all(
                            c.version_number == case.get("expected_version", 1)
                            for c in result.cards
                        ),
                        "card_limit": len(result.cards) <= query.limit,
                        "repeat_results_stable": stable,
                        "uncertainty_preserved": all(
                            c.verification == "uncertain"
                            for c in result.cards
                            if c.decision_state == "contested"
                        )
                        if compact
                        else True,
                        "total_bytes_bounded": encoded_size(result) <= ContextBudget().max_bytes
                        if compact
                        else True,
                        "expected_omission": omitted
                        if compact and case.get("expect_omission")
                        else True,
                        "claim_preserved_or_marked": all(
                            c.content == contents[c.memory_id]
                            or (omitted and c.content.startswith("[Full claim omitted;"))
                            for c in result.cards
                        ),
                        "conflict_limit_warning": "CONFLICT_ALTERNATIVES_OMITTED" in result.warnings
                        if compact and case.get("conflict") and query.limit == 1
                        else True,
                        "design_recall_at_limit": len(set(returned) & set(case["relevant"]))
                        >= case.get(
                            "minimum_relevant_returned", min(query.limit, len(case["relevant"]))
                        )
                        if compact
                        else True,
                        "capacity_omission_visible": "CONTEXT_CARDS_OMITTED" in result.warnings
                        and len(returned) < len(case["relevant"])
                        if compact and case.get("expect_card_omission")
                        else True,
                        "missing_index_visible": "EMBEDDING_UNAVAILABLE" in result.warnings
                        if compact and case.get("expect_degraded")
                        else True,
                    }
                    # Full text/evidence must remain inspectable after context compaction.
                    checks["inspection_preserved"] = all(
                        any(
                            v.content == contents[c.memory_id]
                            and v.source.evidence == contents[c.memory_id]
                            for v in MemoryService(session, owner).inspect(c.memory_id).history
                        )
                        for c in result.cards
                    )
                    rows.append(
                        {
                            "case": case["id"],
                            "partition": case["partition"],
                            "mode": mode,
                            "returned": returned,
                            "relevant": case["relevant"],
                            **metrics(returned, case["relevant"]),
                            "checks": checks,
                            "warnings": result.warnings,
                            "response_bytes": encoded_size(result),
                            "query_embedding_calls_per_execution": embedder.calls / (repeats + 1),
                            "latency": percentiles(samples),
                            "elapsed_ms": samples,
                            "full_claim_cards": sum(
                                c.content == contents[c.memory_id] for c in result.cards
                            ),
                            "case_records": len(case["records"]),
                        }
                    )
            return {
                "schema_version": 1,
                "recorded_at": datetime.now(UTC).isoformat(),
                "dataset_sha256": hashlib.sha256(
                    json.dumps(dataset, sort_keys=True).encode()
                ).hexdigest(),
                "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "label_status": dataset["label_status"],
                "independent_review_complete": False,
                "model_quality_measured": False,
                "hosted_requests": 0,
                "timing_scope": (
                    "in_process_service_and_real_postgresql_warm_queries_"
                    "excludes_network_and_hosted_latency"
                ),
                "embedding_source": "authored_4d_fixture_vectors_no_semantic_model",
                "postgres": postgres,
                "python": platform.python_version(),
                "scale_distractors": scale,
                "all_design_checks_pass": all(all(r["checks"].values()) for r in rows),
                "summary": summarize(rows),
                "rows": rows,
            }
    finally:
        try:
            with Session(engine) as session:
                for actual_owner, memory_id in reversed(created):
                    if session.get(Memory, memory_id) is not None:
                        MemoryService(session, actual_owner).forget(memory_id)
                for model in (WorkItem, ReindexJob, EmbeddingModel):
                    session.execute(
                        delete(model).where(model.developer_id.in_([owner, owner + "-foreign"]))
                    )
                session.commit()
        finally:
            engine.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--scale", type=int, default=0, help="0..2000 same-project distractors")
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise ValueError("Do not overwrite evidence")
        url = os.environ.get("CONTEXTBRIDGE_TEST_DATABASE_URL")
        if not url:
            raise ValueError("Missing test store")
        report = evaluate(
            url,
            json.loads(CASES.read_text(encoding="utf-8")),
            repeats=args.repeats,
            scale=args.scale,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as output:
            output.write(json.dumps(report, indent=2) + "\n")
        print(
            f"Benchmark rows: {len(report['rows'])}; "
            f"design checks: {report['all_design_checks_pass']}"
        )
        return int(not report["all_design_checks_pass"])
    except (
        ValueError,
        KeyError,
        TypeError,
        ModuleError,
        MemoryServiceError,
        SQLAlchemyError,
        OSError,
    ):
        print("Benchmark failed; use a new output path and an empty migrated pgvector _test store.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

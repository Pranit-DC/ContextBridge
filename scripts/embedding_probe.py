"""Explicit, capped synthetic Cloudflare verification. Never called by ordinary tests/CI.

API and fresh MCP SDK sessions run in process; provider HTTP and PostgreSQL are real.
The transport instrumentation counts requests and stops on the first HTTP/provider failure.
"""

import argparse
import asyncio
import hashlib
import json
import logging
import secrets
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from unittest.mock import patch
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient
from mcp import Client
from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from contextbridge.api import create_app
from contextbridge.background.runner import WorkRunner
from contextbridge.background.runtime import load_providers
from contextbridge.config import Settings
from contextbridge.db import make_engine, make_session_factory
from contextbridge.engine.errors import ModuleError
from contextbridge.engine.index_queue import queue_missing_indexes
from contextbridge.mcp_adapter.config import MCPSettings
from contextbridge.mcp_adapter.gateway import MemoryGateway
from contextbridge.mcp_adapter.server import create_server
from contextbridge.models import Base, MemoryEmbedding, WorkItem
from contextbridge.persistence.vectors import vector_available
from contextbridge.retrieval.cloudflare import DIMENSIONS, MODEL_ID, CloudflareEmbeddingBackend

ROOT = Path(__file__).resolve().parents[1]
QUERY = "Which storage system handles durable relational records?"
DOCUMENTS = [
    "Use PostgreSQL as the application's primary database.",
    "Use Ruff to format Python code.",
    "Send application logs as JSON to standard output.",
    "Use GitHub Actions to run automated tests.",
]


class ProbeFailure(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def require(condition, code):
    if not condition:
        raise ProbeFailure(code)


class BudgetTransport(httpx.BaseTransport):
    def __init__(self, limit):
        self.limit, self.calls, self.failed = limit, 0, False
        self.lock = Lock()
        self.network = httpx.HTTPTransport(retries=0, trust_env=False)

    def handle_request(self, request):
        with self.lock:
            if self.failed or self.calls >= self.limit:
                raise ModuleError("PROVIDER_UNAVAILABLE")
            self.calls += 1
            try:
                response = self.network.handle_request(request)
            except Exception:
                self.failed = True
                raise ModuleError("EMBEDDING_UNAVAILABLE") from None
            if response.status_code != 200:
                self.failed = True
            return response

    def close(self):
        # Each backend client exits after a call; the probe owns the shared transport lifetime.
        pass


def safe_database(value):
    url = make_url(value)
    require(
        url.drivername == "postgresql+psycopg"
        and url.host in {"127.0.0.1", "localhost"}
        and bool(url.database)
        and url.database.endswith("_test"),
        "REQUIRES_LOOPBACK_TEST_DATABASE",
    )
    return value


def empty_database(sessions):
    with sessions() as db:
        for table in Base.metadata.sorted_tables:
            require(
                db.scalar(select(func.count()).select_from(table)) == 0,
                "TEST_DATABASE_NOT_EMPTY",
            )
        require(vector_available(db), "PGVECTOR_REQUIRED")


def index(sessions, settings, budget):
    queued = queue_missing_indexes(sessions, settings)
    runner = WorkRunner(sessions, settings, load_providers(settings, sessions))
    with sessions() as db:
        ids = list(db.scalars(select(WorkItem.id).where(WorkItem.kind == "reindex")))
    for item in ids:
        runner.run(item)
        require(not budget.failed, "PROVIDER_HTTP_FAILURE")
        require(runner.inspect(item)["status"] == "succeeded", "INDEX_NOT_SUCCEEDED")
    return queued


def check_search(result, memory_id, version, report, label):
    require(not result["degraded"], "SEARCH_DEGRADED")
    ids = [c["memory_id"] for c in result["cards"]]
    require(memory_id in ids, "EXPECTED_MEMORY_NOT_RETRIEVED")
    rank = ids.index(memory_id) + 1
    require(rank == 1, "INTENDED_MEMORY_NOT_FIRST")
    require(result["cards"][rank - 1]["version_number"] == version, "WRONG_VERSION")
    report["checks"][label] = {"passed": True, "intended_memory_rank": rank}
    return rank


def run(settings, sessions, budget, report):
    empty_database(sessions)
    with TestClient(
        create_app(settings),
        headers={"Authorization": f"Bearer {settings.api_token.get_secret_value()}"},
    ) as api:
        ids = []
        for number, content in enumerate(DOCUMENTS):
            result = api.post(
                "/v1/memories",
                json={
                    "request_id": str(uuid4()),
                    "scope": "project",
                    "project_id": "embedding-probe",
                    "type": "DECISION",
                    "content": content,
                    "source": {
                        "kind": "user",
                        "agent": "synthetic-probe",
                        "session": "synthetic",
                        "interaction": f"synthetic-{number}",
                        "evidence": content,
                    },
                },
            )
            require(result.status_code == 201, "SYNTHETIC_WRITE_FAILED")
            ids.append(result.json()["id"])
        target = ids[0]
        require(index(sessions, settings, budget) == len(DOCUMENTS), "INDEX_DISCOVERY_FAILED")
        with sessions() as db:
            require(db.scalar(select(MemoryEmbedding.dimensions)) == DIMENSIONS, "WRONG_WIDTH")
        report["observed_dimensions"] = DIMENSIONS
        before = budget.calls
        require(
            index(sessions, settings, budget) == 0 and before == budget.calls, "REPLAY_REEMBEDDED"
        )
        report["checks"]["index_restart_replay"] = {"passed": True}
        historic = datetime.now(UTC).isoformat()
        result = api.post(
            "/v1/retrieval/search",
            json={
                "schema_version": 1,
                "scope": "project",
                "project_id": "embedding-probe",
                "query": QUERY,
                "limit": 1,
            },
        )
        require(result.status_code == 200 and not budget.failed, "API_SEARCH_FAILED")
        check_search(result.json(), target, 1, report, "api_paraphrase_among_three_distractors")

        def agent(name):
            return Client(
                create_server(
                    MemoryGateway(
                        MCPSettings(
                            _env_file=None,
                            api_token=settings.api_token,
                            project_id="embedding-probe",
                            agent_id=name,
                        ),
                        httpx.ASGITransport(app=api.app),
                    )
                )
            )

        async def mcp():
            async with agent("probe-first") as first:
                found = await first.call_tool("memory_retrieve", {"query": QUERY, "limit": 1})
                require(not found.is_error and not budget.failed, "MCP_SEARCH_FAILED")
                check_search(found.structured_content, target, 1, report, "fresh_mcp_paraphrase")
                corrected = await first.call_tool(
                    "memory_update",
                    {
                        "memory_id": target,
                        "expected_version": 1,
                        "content": "Use SQLite as the application's primary database.",
                        "source": {
                            "kind": "user",
                            "interaction": "synthetic-correction",
                            "evidence": "Use SQLite as the application's primary database.",
                        },
                    },
                )
                require(not corrected.is_error, "CORRECTION_FAILED")
            require(index(sessions, settings, budget) == 1, "CORRECTION_NOT_INDEXED")
            async with agent("probe-fresh") as fresh:
                found = await fresh.call_tool("memory_retrieve", {"query": QUERY, "limit": 1})
                require(not found.is_error and not budget.failed, "FRESH_MCP_SEARCH_FAILED")
                check_search(found.structured_content, target, 2, report, "correction_fresh_mcp")
                old = await fresh.call_tool(
                    "memory_retrieve", {"query": QUERY, "limit": 1, "as_of": historic}
                )
                require(not old.is_error and not budget.failed, "HISTORY_SEARCH_FAILED")
                check_search(old.structured_content, target, 1, report, "historical_vector")
                forgotten = await fresh.call_tool("memory_forget", {"memory_id": target})
                require(not forgotten.is_error, "FORGET_FAILED")
            async with agent("probe-after-forget") as fresh:
                found = await fresh.call_tool("memory_retrieve", {"query": QUERY, "limit": 4})
                require(not found.is_error and not budget.failed, "POST_FORGET_SEARCH_FAILED")
                require(
                    all(c["memory_id"] != target for c in found.structured_content["cards"]),
                    "FORGOTTEN_MEMORY_RETURNED",
                )
                report["checks"]["forget_fresh_mcp"] = {"passed": True}

        asyncio.run(mcp())
        with sessions() as db:
            require(
                db.scalar(select(func.count()).select_from(MemoryEmbedding)) == 3,
                "FORGOTTEN_VECTORS_REMAIN",
            )
        for memory_id in ids[1:]:
            require(api.delete(f"/v1/memories/{memory_id}").status_code == 204, "CLEANUP_FAILED")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", required=True)
    parser.add_argument("--confirm-free-plan", action="store_true", required=True)
    parser.add_argument("--credentials-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--max-calls", type=int, choices=range(1, 21), default=20)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    budget = BudgetTransport(args.max_calls)
    report = {
        "schema_version": 1,
        "model_id": MODEL_ID,
        "recorded_at": datetime.now(UTC).isoformat(),
        "account_plan": "Free (user confirmed)",
        "request_limit": args.max_calls,
        "data": "four short synthetic memories only",
        "checks": {},
        "api_mcp_transport": "in-process API and fresh MCP SDK sessions; real provider HTTPS",
        "billing_usage": "not measured; no paid upgrade authorized",
        "accuracy_claim": "single synthetic example, not a general quality evaluation",
    }
    engine = None
    try:
        settings = Settings(
            _env_file=args.credentials_file,
            database_url=safe_database(args.database_url),
            api_token=secrets.token_hex(24),
            developer_id="embedding-probe",
            capture_project_id="embedding-probe",
            capture_allow_developer=False,
            worker_factory=None,
            integration_factory=None,
            worker_max_attempts=1,
        )
        require(settings.embedding_only, "CLOUDFLARE_CONFIGURATION_REQUIRED")
        engine = make_engine(settings)
        sessions = make_session_factory(engine)
        with patch(
            "contextbridge.runtime.CloudflareEmbeddingBackend",
            lambda **options: CloudflareEmbeddingBackend(**options, transport=budget),
        ):
            run(settings, sessions, budget, report)
        report["status"] = "passed"
    except Exception as error:
        report["status"] = "failed"
        report["reason_code"] = (
            error.code if isinstance(error, (ProbeFailure, ModuleError)) else "PROBE_UNAVAILABLE"
        )
    finally:
        if engine is not None:
            engine.dispose()
        budget.network.close()
    report["requests_sent"] = budget.calls
    report["source_sha256"] = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [ROOT / "src/contextbridge/retrieval/cloudflare.py", Path(__file__)]
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ["status", "requests_sent", "checks"]}))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

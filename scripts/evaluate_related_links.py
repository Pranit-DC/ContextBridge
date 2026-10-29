"""Offline #8 comparison on an empty dedicated _test store; no model requests."""

import argparse
import json
import os
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from contextbridge.config import Settings
from contextbridge.contracts import RetrievalQuery
from contextbridge.engine.errors import EngineError
from contextbridge.engine.modules import ModuleGateway
from contextbridge.engine.retrieval import RetrievalService
from contextbridge.models import Memory
from contextbridge.retrieval import RetrievalConfig, Retriever
from contextbridge.schemas import CreateMemory
from contextbridge.service import MemoryService

CASES = Path(__file__).resolve().parents[1] / "evaluation" / "related-links" / "cases.json"
OWNER = "related-evaluation"


def evaluate(url, dataset):
    if not make_url(url).database or not make_url(url).database.endswith("_test"):
        raise ValueError("A dedicated test database is required")
    engine = create_engine(url)
    created, results = [], []
    try:
        with Session(engine) as session:
            if session.scalar(select(func.count()).select_from(Memory)):
                raise ValueError("Evaluation requires an empty test store")
        for case in dataset["cases"]:
            project = f"related-{case['id']}"
            labels = {}
            for record in case["records"]:
                owner = record.get("owner", OWNER)
                with Session(engine, expire_on_commit=False) as session:
                    saved = MemoryService(session, owner).create(
                        CreateMemory(
                            request_id=uuid4(),
                            scope="project",
                            project_id=record.get("project_id", project),
                            type="FACT",
                            content=record["content"],
                            conditions=record.get("conditions", {}),
                            source={
                                "kind": "user",
                                "agent": "synthetic-evaluation",
                                "session": case["id"],
                                "interaction": record["id"],
                                "evidence": record.get("evidence", record["content"]),
                            },
                        )
                    )
                    created.append((owner, saved.id))
                    labels[saved.id] = record["id"]
            settings = Settings(
                _env_file=None,
                database_url=url,
                api_token="synthetic-offline-evaluation-token",
                developer_id=OWNER,
            )
            row = {"id": case["id"]}
            for name, expand in [("baseline", False), ("expanded", True)]:
                with Session(engine) as session:
                    modules = ModuleGateway(
                        retriever=Retriever(RetrievalConfig(expand_graph=expand))
                    )
                    result = RetrievalService(session, settings, modules).search(
                        RetrievalQuery(
                            schema_version=1,
                            scope="project",
                            project_id=project,
                            query=case["query"],
                            limit=case.get("limit", 3),
                        )
                    )
                    row[name] = [labels[card.memory_id] for card in result.cards]
            row["expected_baseline"] = case["baseline"]
            row["expected_expanded"] = case["expanded"]
            row["matches_design_expectation"] = all(
                row[name] == case[name] for name in ["baseline", "expanded"]
            )
            results.append(row)
        return {
            "mode": "real_postgresql_lexical_and_optional_graph",
            "label_status": dataset["label_status"],
            "hosted_requests": 0,
            "semantic_quality_measured": False,
            "independent_review_complete": False,
            "case_count": len(results),
            "matching_design_cases": sum(row["matches_design_expectation"] for row in results),
            "rows": results,
        }
    finally:
        try:
            for owner, memory_id in reversed(created):
                with Session(engine) as session:
                    if session.get(Memory, memory_id) is not None:
                        MemoryService(session, owner).forget(memory_id)
        finally:
            engine.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise ValueError("Do not overwrite evidence")
        url = os.environ.get("CONTEXTBRIDGE_TEST_DATABASE_URL")
        if not url:
            raise ValueError("Missing test database")
        report = evaluate(url, json.loads(CASES.read_text()))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(f"Design cases matched: {report['matching_design_cases']}/{report['case_count']}")
        return int(report["matching_design_cases"] != report["case_count"])
    except (ValueError, EngineError, SQLAlchemyError, OSError):
        print(
            "Related-link evaluation failed; use an empty migrated _test store "
            "and a new output path."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

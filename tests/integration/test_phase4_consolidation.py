"""Integrated consolidation preserves sources; HTTP judgements are synthetic substitutes."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from contextbridge.engine.consolidation import ConsolidationService
from contextbridge.engine.errors import ModuleError
from contextbridge.models import Memory, MemoryEdge
from contextbridge.service import MemoryService
from tests.integration.phase4_fakes import HostedReplay
from tests.integration.retrieval_fakes import create, query
from tests.integration.write_fakes import Harness
from tests.test_validation import payload

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("case", ["rare", "disagreement", "uncertain", "conditions"])
def test_current_hosted_consolidator_keeps_rare_facts_evidence_and_disagreements(
    database, monkeypatch, tmp_path, case
):
    texts = ["Use PostgreSQL database.", "After error E731 run repair_index.py with --dry-run."]
    if case == "disagreement":
        texts[1] = "Use SQLite as the only database."
    originals = [
        create(
            database,
            text,
            source=payload()["source"] | {"interaction": f"source-{i}", "evidence": text},
            conditions={"environment": "production"} if case == "conditions" and i else {},
        )
        for i, text in enumerate(texts)
    ]
    harness = Harness(database)

    def respond(name, value):
        if name == "GroupingResponse":
            return {"groups": [[r["memory"]["version"]["id"] for r in value["records"]]]}
        if name == "VerificationResponse":
            assert {r["memory"]["version"]["source"]["evidence"] for r in value["records"]} == set(
                texts
            )
            return {
                "support": {
                    "rare": "supported",
                    "disagreement": "unsupported",
                    "uncertain": "uncertain",
                }[case]
            }
        raise AssertionError(name)

    replay = HostedReplay(harness, monkeypatch, tmp_path, respond)
    with Session(database[1]) as db:
        service = ConsolidationService(db, harness.settings)
        args = (query(), [str(m.version.id) for m in originals], str(uuid4()))
        if case == "conditions":
            with pytest.raises(ModuleError, match="OUT_OF_SCOPE"):
                service.enqueue(*args)
            assert not replay.requests
            return
        job = service.enqueue(*args)
        result = service.process(job, replay.providers.modules.consolidator)
        assert service.process(job, replay.providers.modules.consolidator) == result
        if case == "rare":
            assert result["status"] == "succeeded" and len(result["memory_ids"]) == 1
            summary_id = UUID(result["memory_ids"][0])
            summary = MemoryService(db, "developer-a").inspect(summary_id)
            assert all(text in summary.memory.version.content for text in texts)
            edges = list(db.scalars(select(MemoryEdge)))
            assert {e.relation for e in edges} == {"derived_from"}
            assert {e.to_version_id for e in edges} == {m.version.id for m in originals}
            assert {e.from_version_id for e in edges} == {summary.memory.version.id}
            assert db.scalar(select(func.count()).select_from(Memory)) == 3
            for original in originals:
                saved = MemoryService(db, "developer-a").inspect(original.id)
                assert saved.memory.version.source == original.version.source
                assert saved.memory.version.content == original.version.content
            with harness.client() as api:
                sources = api.get(f"/v1/memories/{summary_id}/sources")
                assert sources.status_code == 200
                assert all(text in sources.text for text in texts)
            MemoryService(db, "developer-a").forget(originals[0].id)
            assert db.get(Memory, summary_id) is None
            assert db.get(Memory, originals[1].id) is not None
            assert db.scalar(select(MemoryEdge)) is None
        else:
            assert not result["memory_ids"]
            assert db.scalar(select(func.count()).select_from(Memory)) == 2
            assert db.scalar(select(MemoryEdge)) is None
    assert replay.snapshot() == {"calls": {"groq": 2, "cloudflare": 0}, "stopped": False}

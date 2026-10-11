"""Actual PostgreSQL/shared-engine execution with Om's module and synthetic labels."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from contextbridge.config import Settings
from contextbridge.engine.consolidation import ConsolidationService
from contextbridge.formation import Consolidator
from contextbridge.models import ConsolidationJob, ConsolidationSource, Memory, MemoryEdge
from contextbridge.schemas import UpdateMemory
from contextbridge.service import MemoryService
from tests.conftest import TEST_TOKEN
from tests.formation.test_consolidation import Group, Verify
from tests.integration.retrieval_fakes import create, query

pytestmark = pytest.mark.integration


def setup(database):
    settings = Settings(
        _env_file=None,
        database_url=database[0],
        api_token=TEST_TOKEN,
        developer_id="developer-a",
        capture_project_id="contextbridge",
    )
    rare_lesson = "Never drop audit.sql; retain its 7-day backup."
    sources = [
        create(database),
        create(
            database,
            rare_lesson,
            type="LESSON",
            source={
                "kind": "user",
                "agent": "synthetic-fixture",
                "session": "o4-postgres",
                "interaction": "rare-lesson",
                "evidence": rare_lesson,
            },
        ),
    ]
    with Session(database[1], expire_on_commit=False) as session:
        job = ConsolidationService(session, settings).enqueue(
            query(), [str(source.version.id) for source in sources], str(uuid4())
        )
    return settings, sources, job


def process(database, settings, job, module):
    with Session(database[1], expire_on_commit=False) as session:
        return ConsolidationService(session, settings).process(job, module)


def test_actual_om_proposals_commit_edges_preserve_rare_facts_and_replay(database):
    settings, sources, job = setup(database)
    provider = Group()
    module = Consolidator(provider, Verify())
    result = process(database, settings, job, module)
    assert result["status"] == "succeeded" and len(result["memory_ids"]) == 1
    assert process(database, settings, job, module) == result
    assert len(provider.calls) == 1
    with Session(database[1]) as session:
        summary = MemoryService(session, "developer-a").inspect(UUID(result["memory_ids"][0]))
        assert summary.memory.type == "STATE"
        for source in sources:
            assert source.version.content in summary.memory.version.content
            original = MemoryService(session, "developer-a").inspect(source.id)
            assert original.memory.version == source.version
        assert {edge.to_version_id for edge in summary.edges} == {s.version.id for s in sources}
        assert all(edge.relation == "derived_from" for edge in summary.edges)
        assert session.scalar(select(func.count()).select_from(Memory)) == 3
        assert session.get(ConsolidationJob, job).proposals is None


@pytest.mark.parametrize("label", ["unsupported", "uncertain"])
def test_abstention_does_not_write_summary_or_mutate_sources(database, label):
    settings, _, job = setup(database)
    result = process(database, settings, job, Consolidator(Group(), Verify(label)))
    assert result["status"] == "succeeded" and result["memory_ids"] == []
    with Session(database[1]) as session:
        assert session.scalar(select(func.count()).select_from(Memory)) == 2
        assert session.scalar(select(MemoryEdge)) is None


@pytest.mark.parametrize("phase", ["group", "verify"])
def test_changed_source_during_om_provider_call_is_rejected_by_engine(database, phase):
    settings, sources, job = setup(database)

    def mutate():
        with Session(database[1]) as session:
            MemoryService(session, "developer-a").update(
                sources[0].id,
                UpdateMemory(
                    expected_version=1, content="Use SQLite.", source=sources[0].version.source
                ),
            )

    class Change(Group, Verify):
        def group(self, records):
            if phase == "group":
                mutate()
            return super().group(records)

        def verify(self, proposal, records):
            if phase == "verify":
                mutate()
            return "supported"

    change = Change()
    result = process(database, settings, job, Consolidator(change, change))
    assert result["status"] == "failed" and result["reason_codes"] == ["VERSION_CONFLICT"]
    with Session(database[1]) as session:
        assert session.scalar(select(func.count()).select_from(Memory)) == 2
        assert (
            session.scalar(select(MemoryEdge).where(MemoryEdge.relation == "derived_from")) is None
        )
        assert (
            session.scalar(select(MemoryEdge).where(MemoryEdge.relation == "supersedes"))
            is not None
        )
        assert session.get(ConsolidationJob, job).proposals is None


@pytest.mark.parametrize("phase", ["group", "verify"])
def test_forget_during_om_provider_call_cancels_without_saving_content(database, phase):
    settings, sources, job = setup(database)

    def forget():
        with Session(database[1]) as session:
            MemoryService(session, "developer-a").forget(sources[0].id)

    class Forget(Group, Verify):
        def group(self, records):
            if phase == "group":
                forget()
            return super().group(records)

        def verify(self, proposal, records):
            if phase == "verify":
                forget()
            return "supported"

    provider = Forget()
    module = Consolidator(provider, provider)
    result = process(database, settings, job, module)
    assert result["status"] == "cancelled" and result["memory_ids"] == []
    assert process(database, settings, job, module) == result
    with Session(database[1]) as session:
        saved = session.get(ConsolidationJob, job)
        assert saved.proposals is saved.request_fingerprint is None
        assert session.scalar(select(ConsolidationSource)) is None
        assert session.scalar(select(MemoryEdge)) is None
        assert session.scalar(select(func.count()).select_from(Memory)) == 1


def test_forgetting_a_source_removes_actual_om_summary_and_preserves_other_source(database):
    settings, sources, job = setup(database)
    result = process(database, settings, job, Consolidator(Group(), Verify()))
    summary_id = UUID(result["memory_ids"][0])
    with Session(database[1]) as session:
        MemoryService(session, "developer-a").forget(sources[0].id)
    with Session(database[1]) as session:
        assert session.get(Memory, summary_id) is None
        assert session.get(Memory, sources[1].id) is not None
        assert session.scalar(select(MemoryEdge)) is None

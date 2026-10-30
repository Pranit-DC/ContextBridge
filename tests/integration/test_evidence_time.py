"""V2 integration uses scripted model responses; no hosted calls or teammate module edits."""

import json
from copy import deepcopy
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from contextbridge.engine.modules import ModuleGateway
from contextbridge.evidence_time.runtime import BundleAwareExtractor, BundleAwareVerifier
from contextbridge.formation.admission import AdmissionPolicy
from contextbridge.models import (
    CandidateProvenance,
    CaptureBundle,
    CaptureCandidate,
    CaptureEvent,
    CaptureJob,
    Memory,
    MemoryVersion,
    VersionProvenance,
)
from tests.engine.fakes import fixture
from tests.integration.write_fakes import Harness

pytestmark = pytest.mark.integration


class Chat:
    settings = SimpleNamespace(model="scripted-test")

    def __init__(self):
        self.calls = []
        self.claim = {
            "temporal_relation": "state_transition",
            "content": "Use SQLite as the database.",
            "type": "DECISION",
            "conditions": [],
            "claim_key": "project.database.primary",
            "confidence": 0.95,
            "usefulness": 0.95,
            "evidence": [
                {"message_id": "s0m0", "quote": "SQLite is the proposed database."},
                {"message_id": "s1m0", "quote": "Adopt that database yesterday."},
            ],
        }
        self.audit = {
            "support": "supported",
            "scope": "bound",
            "kind": "DECISION",
            "temporal_relation": "state_transition",
            "conditions": [],
        }

    def complete(self, model, prompt, payload, schema):
        self.calls.append((schema.__name__, deepcopy(payload)))
        return json.dumps(
            {"claims": [self.claim]}
            if schema.__name__ == "BundleClaims"
            else {
                "checks": [
                    {"candidate_id": item["candidate_id"], **self.audit}
                    for item in payload["candidates"]
                ]
            }
        )


def bundle():
    events = []
    for i, (time, content) in enumerate(
        [
            ("2026-10-09T09:00:00+05:30", "SQLite is the proposed database."),
            ("2026-10-10T10:00:00+05:30", "Adopt that database yesterday."),
        ]
    ):
        event = fixture("captured-event")
        event.update(
            event_id=str(uuid4()),
            occurred_at=time,
            source_timezone="Asia/Kolkata",
            interaction=f"turn-{i}",
        )
        event["messages"] = [{"message_id": "original", "role": "user", "content": content}]
        events.append(event)
    return {"schema_version": 2, "bundle_id": str(uuid4()), "events": events}


def setup(database, **settings):
    harness = Harness(database, capture_evidence_v2_enabled=True, **settings)
    chat = Chat()
    sessions = sessionmaker(database[1])
    extractor = BundleAwareExtractor(harness.extractor, chat, sessions, harness.settings)
    verifier = BundleAwareVerifier(None, chat, sessions, harness.settings)

    def lookup(identifier):
        with sessions() as session:
            return session.scalar(
                select(CaptureEvent.payload).where(CaptureEvent.event_id == UUID(identifier))
            )

    harness.extractor = extractor
    harness.modules = ModuleGateway(
        extractor=extractor, admission=AdmissionPolicy(verifier, lookup)
    )
    return harness, chat


def enqueue(harness, payload):
    with harness.client() as client:
        response = client.post("/v2/interactions/bundles", json=payload)
    assert response.status_code == 202, response.text
    return response.json()["job_id"]


def total(database, model):
    with Session(database[1]) as session:
        return session.scalar(select(func.count()).select_from(model))


def test_bundle_end_to_end_preserves_both_quotes_original_offset_and_replay(database):
    harness, chat = setup(database)
    payload = bundle()
    job = enqueue(harness, payload)
    assert enqueue(harness, payload) == job
    result = harness.process(job)
    assert result.status == "succeeded", result
    assert len(result.memory_ids) == 1
    assert [c[0] for c in chat.calls] == ["BundleClaims", "BatchAudit"]
    memory = result.memory_ids[0]
    with harness.client() as client:
        data = client.post(
            "/v2/inspection/provenance",
            json={"scope": "project", "project_id": "contextbridge", "memory_id": str(memory)},
        ).json()
        detail = client.get(f"/v1/memories/{memory}").json()
    fragments = data["metadata"]["fragments"]
    assert len(fragments) == 2
    assert fragments[1]["occurred_at"] == "2026-10-10T10:00:00+05:30"
    assert fragments[0]["event_id"] == payload["events"][0]["event_id"]
    assert fragments[0]["message_id"] == "original"
    temporal = data["metadata"]["temporal"]
    assert temporal["precision"] == "day"
    assert temporal["earliest"] == "2026-10-08T18:30:00Z"
    assert temporal["guaranteed_from"] == "2026-10-09T18:30:00Z"
    source = detail["memory"]["version"]["source"]
    assert source["kind"] == "tool" and all(f["quote"] in source["evidence"] for f in fragments)
    assert harness.process(job).memory_ids == [memory]
    assert len(chat.calls) == 2
    assert total(database, MemoryVersion) == total(database, VersionProvenance) == 1


@pytest.mark.parametrize(
    "change,status", [("zone", 409), ("project", 422), ("unknown_zone", 422), ("assistant", 202)]
)
def test_bundle_replay_binding_and_source_authority(database, change, status):
    harness, chat = setup(database)
    payload = bundle()
    job = enqueue(harness, payload)
    changed = deepcopy(payload)
    if change == "zone":
        changed["events"][0]["source_timezone"] = "UTC"
    elif change == "project":
        changed["events"][0]["project_id"] = "other"
    elif change == "unknown_zone":
        changed["events"][0]["source_timezone"] = "Unknown/Zone"
    else:
        changed["bundle_id"] = str(uuid4())
        changed["events"][0]["messages"][0]["role"] = "assistant"
    with harness.client() as client:
        response = client.post("/v2/interactions/bundles", json=changed)
    assert response.status_code == status, response.text
    if change == "assistant":
        assert harness.process(response.json()["job_id"]).status == "failed"
        assert total(database, Memory) == 0
    else:
        assert total(database, CaptureJob) == 1
        assert harness.process(job).status == "succeeded"


@pytest.mark.parametrize(
    "audit,expected",
    [
        ("unsupported", "succeeded"),
        ("uncertain", "deferred"),
        ("wrong_relation", "deferred"),
        ("other", "succeeded"),
    ],
)
def test_independent_audit_blocks_unsupported_scope_and_time(database, audit, expected):
    harness, chat = setup(database)
    if audit == "wrong_relation":
        chat.audit["temporal_relation"] = "context_only"
    elif audit == "other":
        chat.audit["scope"] = "other"
    else:
        chat.audit["support"] = audit
    result = harness.process(enqueue(harness, bundle()))
    assert result.status == expected, result
    assert total(database, Memory) == total(database, VersionProvenance) == 0


def test_feature_off_cannot_ingest_or_process_a_queued_bundle(database):
    harness, chat = setup(database)
    job = enqueue(harness, bundle())
    harness.settings.capture_evidence_v2_enabled = False
    with harness.client() as client:
        assert client.post("/v2/interactions/bundles", json=bundle()).status_code == 503
    assert harness.process(job).status == "queued"
    assert chat.calls == []


def test_forget_erases_all_quotes_and_ephemeral_sidecars(database):
    harness, _ = setup(database)
    memory = harness.process(enqueue(harness, bundle())).memory_ids[0]
    assert total(database, CaptureBundle) == total(database, CandidateProvenance) == 1
    with harness.client() as client:
        assert client.delete(f"/v1/memories/{memory}").status_code == 204
        assert (
            client.post(
                "/v2/inspection/provenance",
                json={"scope": "project", "project_id": "contextbridge", "memory_id": str(memory)},
            ).status_code
            == 404
        )
    for model in [Memory, MemoryVersion, VersionProvenance, CaptureBundle, CandidateProvenance]:
        assert total(database, model) == 0
    with Session(database[1]) as session:
        assert session.scalar(select(CaptureEvent.payload)) is None
        assert session.scalar(select(CaptureCandidate.payload)) is None


def test_expiration_erases_ephemeral_provenance_but_preserves_durable_evidence(database):
    from datetime import UTC, datetime, timedelta

    from contextbridge.engine.ingestion import IngestionService

    harness, _ = setup(database)
    harness.process(enqueue(harness, bundle()))
    with Session(database[1]) as session:
        session.execute(
            update(CaptureEvent).values(
                received_at=datetime.now(UTC) - timedelta(days=2),
                expires_at=datetime.now(UTC) - timedelta(seconds=1),
            )
        )
        session.commit()
        IngestionService(session, harness.settings).expire()
    assert total(database, CaptureBundle) == total(database, CandidateProvenance) == 0
    assert total(database, VersionProvenance) == 1


def test_provenance_is_owner_and_project_bound(database):
    harness, _ = setup(database)
    memory = harness.process(enqueue(harness, bundle())).memory_ids[0]
    body = {"scope": "project", "project_id": "other", "memory_id": str(memory)}
    with harness.client() as client:
        assert client.post("/v2/inspection/provenance", json=body).status_code == 404
    other = Harness(database, owner="developer-b")
    body["project_id"] = "contextbridge"
    with other.client() as client:
        assert client.post("/v2/inspection/provenance", json=body).status_code == 404


def test_uncertain_transition_preserves_history_and_labels_both_possibilities(database):
    from datetime import UTC, datetime

    prior = Harness(database)
    memory = prior.process(prior.enqueue(time=datetime(2026, 10, 7, tzinfo=UTC))[0]).memory_ids[0]
    harness, _ = setup(database)
    harness.set_relation("correction")
    result = harness.process(enqueue(harness, bundle()))
    assert result.status == "succeeded" and result.memory_ids == [memory], result
    request = {
        "scope": "project",
        "project_id": "contextbridge",
        "memory_id": str(memory),
        "expected_version": 2,
        "as_of": "2026-10-09T10:00:00Z",
    }
    with harness.client() as client:
        response = client.post("/v2/retrieval/temporal-context", json=request)
        assert response.status_code == 200, response.text
        data = response.json()
        assert [i["role"] for i in data["items"]] == ["possible_before", "possible_after"]
        assert data["warnings"] == ["TRANSITION_TIME_UNCERTAIN"]
        limited = client.post("/v2/retrieval/temporal-context", json={**request, "limit": 1}).json()
        assert limited["warnings"] == ["TRANSITION_TIME_UNCERTAIN", "TEMPORAL_ALTERNATIVES_OMITTED"]
        for at, number in [("2026-10-08T10:00:00Z", 1), ("2026-10-10T10:00:00Z", 2)]:
            applicable = client.post(
                "/v2/retrieval/temporal-context", json={**request, "as_of": at}
            ).json()
            assert applicable["items"][0]["memory"]["version"]["number"] == number
            assert applicable["items"][0]["applicability"] == "applicable"
        assert (
            client.post(
                "/v2/retrieval/temporal-context", json={**request, "expected_version": 1}
            ).status_code
            == 409
        )
        legacy = client.post(
            "/v1/memories/search",
            json={
                "scope": "project",
                "project_id": "contextbridge",
                "query": "database",
                "as_of": request["as_of"],
            },
        ).json()
        assert legacy == []
    with Session(database[1]) as session:
        versions = session.scalars(select(MemoryVersion).order_by(MemoryVersion.number)).all()
        assert versions[0].valid_to.isoformat() == "2026-10-08T18:30:00+00:00"
        assert versions[1].valid_from.isoformat() == "2026-10-09T18:30:00+00:00"
        assert session.get(VersionProvenance, versions[1].id).previous_version_id == versions[0].id


@pytest.mark.parametrize("mutation", ["offset", "time", "fingerprint", "forget"])
def test_stored_extension_is_revalidated_before_durable_write(database, mutation):
    from contextbridge.contracts import CapturedEvent
    from contextbridge.engine.write import WriteEngine

    harness, _ = setup(database)
    job = enqueue(harness, bundle())
    with Session(database[1], expire_on_commit=False) as session:
        engine = WriteEngine(session, harness.settings, harness.modules)
        event = session.scalar(select(CaptureEvent))
        captured = CapturedEvent.model_validate(event.payload)
        candidates = harness.modules.extract(captured)
        engine.save_extraction(UUID(job), candidates)
        engine.prepare(UUID(job), candidates[0].candidate_id)
        extension = session.scalar(select(CandidateProvenance))
        metadata = deepcopy(extension.metadata_json)
        if mutation == "offset":
            metadata["fragments"][0]["end"] = 8000
        elif mutation == "time":
            metadata["temporal"]["earliest"] = "2026-10-01T00:00:00Z"
        elif mutation == "fingerprint":
            metadata["candidate_fingerprint"] = "0" * 64
        else:
            from contextbridge.persistence.capture_cleanup import cancel_capture_jobs

            cancel_capture_jobs(session, [UUID(job)])
        if mutation != "forget":
            extension.metadata_json = metadata
        session.commit()
    result = harness.process(job)
    assert result.status in {"failed", "cancelled"}, result
    assert total(database, Memory) == total(database, VersionProvenance) == 0


def test_rejected_candidate_erases_provenance_payload(database):
    harness, chat = setup(database)
    chat.audit["support"] = "unsupported"
    harness.process(enqueue(harness, bundle()))
    assert total(database, CandidateProvenance) == 0


def test_ambiguous_reference_defers_without_creating_memory(database):
    harness, chat = setup(database)
    chat.claim["temporal_relation"] = "uncertain"
    result = harness.process(enqueue(harness, bundle()))
    assert result.status == "deferred"
    assert total(database, Memory) == total(database, CaptureCandidate) == 0


@pytest.mark.parametrize("during", ["BundleClaims", "BatchAudit"])
def test_forget_during_provider_call_cancels_all_contributing_evidence(database, during):
    prior = Harness(database)
    memory = prior.process(prior.enqueue()[0]).memory_ids[0]
    harness, chat = setup(database)
    original = chat.complete

    def delete_during_call(model, prompt, payload, schema):
        if schema.__name__ == during:
            with prior.client() as client:
                assert client.delete(f"/v1/memories/{memory}").status_code == 204
        return original(model, prompt, payload, schema)

    chat.complete = delete_during_call
    result = harness.process(enqueue(harness, bundle()))
    assert result.status == "cancelled", result
    for model in [Memory, MemoryVersion, CaptureBundle, CandidateProvenance, VersionProvenance]:
        assert total(database, model) == 0
    with Session(database[1]) as session:
        assert set(session.scalars(select(CaptureEvent.payload))) == {None}


def test_v2_write_and_evidence_roll_back_together_after_storage_failure(database):
    from sqlalchemy import event as sql_event
    from sqlalchemy.exc import SQLAlchemyError

    from contextbridge.contracts import CapturedEvent
    from contextbridge.engine.write import WriteEngine

    harness, _ = setup(database)
    job = UUID(enqueue(harness, bundle()))
    with Session(database[1], expire_on_commit=False) as session:
        engine = WriteEngine(session, harness.settings, harness.modules)
        captured = CapturedEvent.model_validate(session.scalar(select(CaptureEvent.payload)))
        candidate = harness.modules.extract(captured)[0]
        engine.save_extraction(job, [candidate])
        engine.prepare(job, candidate.candidate_id)

        def fail_commit(active):
            active.flush()
            assert active.scalar(select(func.count()).select_from(VersionProvenance)) == 1
            raise SQLAlchemyError("private storage diagnostic")

        sql_event.listen(session, "before_commit", fail_commit, once=True)
        with pytest.raises(SQLAlchemyError):
            engine.execute(job, candidate.candidate_id)
        session.rollback()
    assert total(database, Memory) == total(database, VersionProvenance) == 0
    assert harness.process(str(job)).status == "succeeded"
    assert total(database, VersionProvenance) == 1


def test_two_candidate_bundle_uses_one_independent_audit_call(database):
    """Regression: per-candidate quota waits previously exhausted the 120-second lease."""
    harness, chat = setup(database)
    proposal = deepcopy(chat.claim)
    proposal.update(
        content="The proposed database is SQLite.",
        type="FACT",
        claim_key="project.database.proposed",
        temporal_relation="context_only",
        evidence=[chat.claim["evidence"][0]],
    )

    def grouped(model, prompt, payload, schema):
        assert len(chat.calls) < 2, "A third hosted call would require another quota wait"
        if schema.__name__ == "BundleClaims":
            chat.calls.append((schema.__name__, deepcopy(payload)))
            return json.dumps({"claims": [proposal, chat.claim]})
        assert schema.__name__ == "BatchAudit"
        assert len(payload["candidates"]) == 2
        chat.calls.append((schema.__name__, deepcopy(payload)))
        checks = []
        for item in payload["candidates"]:
            candidate = item["candidate"]
            checks.append(
                {
                    **chat.audit,
                    "candidate_id": item["candidate_id"],
                    "kind": candidate["type"],
                    "temporal_relation": item["temporal"]["relation"],
                    "support": "unsupported" if candidate["type"] == "FACT" else "supported",
                }
            )
        return json.dumps({"checks": checks})

    chat.complete = grouped
    result = harness.process(enqueue(harness, bundle()))
    assert result.status == "succeeded" and len(result.memory_ids) == 1, result
    assert [c[0] for c in chat.calls] == ["BundleClaims", "BatchAudit"]
    assert total(database, Memory) == total(database, VersionProvenance) == 1
    assert total(database, CandidateProvenance) == 1  # Rejected proposal has no hidden sidecar.
    from contextbridge.evidence_time.provider import AUDIT, BatchAudit
    from contextbridge.formation.providers.quota import reservation

    assert (
        reservation(SimpleNamespace(max_output_tokens=1024), AUDIT, chat.calls[1][1], BatchAudit)
        <= 8000
    )


@pytest.mark.parametrize("bad", ["missing", "duplicate", "foreign"])
def test_grouped_audit_requires_exact_candidate_identity_set(database, bad):
    harness, chat = setup(database)
    original = chat.complete

    def invalid(model, prompt, payload, schema):
        if schema.__name__ == "BundleClaims":
            return original(model, prompt, payload, schema)
        checks = [{**chat.audit, "candidate_id": payload["candidates"][0]["candidate_id"]}]
        if bad == "missing":
            checks = []
        elif bad == "duplicate":
            checks += checks
        else:
            checks[0]["candidate_id"] = str(uuid4())
        return json.dumps({"checks": checks})

    chat.complete = invalid
    result = harness.process(enqueue(harness, bundle()))
    assert result.status == "failed"
    assert total(database, Memory) == total(database, VersionProvenance) == 0

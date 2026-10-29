"""Opt-in history and paired evidence checks through real API/storage boundaries."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from contextbridge.api import create_app
from contextbridge.config import Settings
from contextbridge.engine.modules import ModuleGateway
from contextbridge.models import MemoryEdge, MemoryVersion
from contextbridge.retrieval.verifier import EvidenceVerifier
from contextbridge.schemas import UpdateMemory
from contextbridge.service import MemoryService
from tests.conftest import TEST_TOKEN
from tests.integration.phase4_fakes import HostedReplay
from tests.integration.retrieval_fakes import create
from tests.integration.write_fakes import Harness
from tests.test_validation import payload

pytestmark = pytest.mark.integration


def source(text):
    return payload()["source"] | {"evidence": text}


def client_for(database, judge=None, owner="developer-a"):
    settings = Settings(
        _env_file=None, database_url=database[0], api_token=TEST_TOKEN, developer_id=owner
    )
    return TestClient(
        create_app(settings, modules=ModuleGateway(), verifier=EvidenceVerifier(judge)),
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    )


def request(memory_id, **changes):
    return {
        "memory_id": str(memory_id),
        "scope": "project",
        "project_id": "contextbridge",
        **changes,
    }


def history(database):
    start = datetime.now(UTC) - timedelta(days=4)
    first = create(database, "Use PostgreSQL.", source=source("Use PostgreSQL."), valid_from=start)
    versions = [first]
    with Session(database[1], expire_on_commit=False) as db:
        for number, text in enumerate(["Use SQLite.", "Use MySQL."], 1):
            versions.append(
                MemoryService(db, "developer-a").update(
                    first.id,
                    UpdateMemory(
                        expected_version=number,
                        content=text,
                        source=source(text),
                        valid_from=start + timedelta(days=number),
                    ),
                )
            )
    return versions


def conflict(database):
    harness = Harness(database)
    initial = harness.process(
        harness.enqueue("Use PostgreSQL.", time=datetime.now(UTC) - timedelta(days=3))[0]
    )
    harness.set_relation("contradiction")
    result = harness.process(
        harness.enqueue("Use SQLite.", time=datetime.now(UTC) - timedelta(days=1))[0]
    )
    assert result.status == "succeeded"
    with Session(database[1]) as db:
        first = MemoryService(db, "developer-a").inspect(initial.memory_ids[0]).memory
        assert db.scalar(select(MemoryEdge.relation)) == "contradicts"
    return first, result.memory_ids[0]


def test_explicit_history_follows_supersedes_without_changing_normal_search(database):
    versions = history(database)
    with client_for(database) as client:
        result = client.post("/v1/retrieval/context", json=request(versions[0].id, depth=3)).json()
        assert [i["content"] for i in result["items"]] == [
            "Use MySQL.",
            "Use SQLite.",
            "Use PostgreSQL.",
        ]
        assert [i["role"] for i in result["items"]] == ["seed", "historical", "historical"]
        assert [i["applicable_at_query"] for i in result["items"]] == [True, False, False]
        assert all(i["status"] == "SUPERSEDED" for i in result["items"][1:])
        current = client.post(
            "/v1/memories/search",
            json={"scope": "project", "project_id": "contextbridge", "query": "PostgreSQL"},
        )
        assert current.json() == []
        limited = client.post("/v1/retrieval/context", json=request(versions[0].id, limit=1)).json()
        assert len(limited["items"]) == 1 and "HISTORICAL_CONTEXT_OMITTED" in limited["warnings"]
        no_history = client.post(
            "/v1/retrieval/context", json=request(versions[0].id, include_history=False)
        ).json()
        assert len(no_history["items"]) == 1
        old = client.post(
            "/v1/retrieval/context",
            json=request(
                versions[0].id,
                as_of=(versions[1].version.valid_from + timedelta(hours=1)).isoformat(),
                expected_version=2,
            ),
        ).json()
        assert old["items"][0]["content"] == "Use SQLite."
        assert old["items"][1]["content"] == "Use PostgreSQL."


@pytest.mark.parametrize("change", ["project", "owner", "conditions", "missing", "stale"])
def test_context_boundaries_fail_without_provider_calls(database, change):
    saved = create(database, conditions={"environment": "production"})
    calls = []

    class Judge:
        def judge(self, *args):
            calls.append(args)
            raise AssertionError("must not call")

    body = request(saved.id, conditions={"environment": "production"}, verify_conflicts=True)
    body.update({"project_id": "other"} if change == "project" else {})
    if change == "conditions":
        body["conditions"] = {}
    if change == "missing":
        body["memory_id"] = str(uuid4())
    if change == "stale":
        body["expected_version"] = 2
    with client_for(
        database, Judge(), owner="other" if change == "owner" else "developer-a"
    ) as client:
        response = client.post("/v1/retrieval/context", json=body)
        assert response.status_code == (409 if change == "stale" else 404)
        assert saved.version.content not in response.text and not calls


def test_conflicts_check_both_evidence_sources_but_never_choose_truth(database):
    first, _ = conflict(database)
    calls = []

    class Judge:
        def judge(self, claim, evidence):
            calls.append((claim, evidence))
            return "supports" if "PostgreSQL" in claim else "contradicts"

    with client_for(database, Judge()) as client:
        body = request(first.id, verify_conflicts=True)
        result = client.post("/v1/retrieval/context", json=body)
        assert result.status_code == 200
        entries = result.json()["items"]
        assert {i["evidence_check"] for i in entries} == {"supports", "contradicts"}
        assert all(i["verification"] == "uncertain" for i in entries)
        assert len(calls) == 2 and all(claim == evidence for claim, evidence in calls)
    with Session(database[1]) as db:
        assert set(db.scalars(select(MemoryVersion.decision_state))) == {"contested"}
        assert len(list(db.scalars(select(MemoryEdge)))) == 1


def test_default_and_nonconflicting_requests_make_no_judge_calls(database):
    first, _ = conflict(database)

    class Judge:
        def judge(self, *args):
            pytest.fail("No evidence check was requested or needed")

    with client_for(database, Judge()) as client:
        assert client.post("/v1/retrieval/context", json=request(first.id)).status_code == 200
        plain = create(database, "A separate fact.")
        assert (
            client.post(
                "/v1/retrieval/context", json=request(plain.id, verify_conflicts=True)
            ).status_code
            == 200
        )


@pytest.mark.parametrize("failure", ["http400", "timeout", "malformed"])
def test_hosted_pair_check_failure_stops_after_first_call_and_hides_details(
    database, monkeypatch, tmp_path, failure
):
    first, _ = conflict(database)
    harness = Harness(database)

    def respond(name, value):
        assert name == "JudgmentResponse"
        if failure == "http400":
            return httpx.Response(400, json={"error": "private-provider-diagnostic"})
        if failure == "timeout":
            raise httpx.ReadTimeout("private-provider-diagnostic")
        return {"judgment": "invalid-private-provider-diagnostic"}

    replay = HostedReplay(harness, monkeypatch, tmp_path, respond)
    with TestClient(
        create_app(
            harness.settings,
            modules=ModuleGateway(),
            context_verifier=replay.providers.context_verifier,
        ),
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    ) as client:
        response = client.post(
            "/v1/retrieval/context", json=request(first.id, verify_conflicts=True)
        )
        assert response.status_code == 200
        assert "VERIFICATION_UNAVAILABLE" in response.json()["warnings"]
        assert "private-provider-diagnostic" not in response.text
        assert len(replay.requests) == 1
        assert all(i["verification"] == "uncertain" for i in response.json()["items"])


def test_forget_during_judgment_cannot_return_stale_content_or_hold_owner_lock(database):
    first, _ = conflict(database)

    class Judge:
        def judge(self, claim, evidence):
            with Session(database[1]) as db:
                MemoryService(db, "developer-a").forget(first.id)
            return "supports"

    with client_for(database, Judge()) as client:
        response = client.post(
            "/v1/retrieval/context", json=request(first.id, verify_conflicts=True)
        )
        assert response.status_code == 404
        assert "PostgreSQL" not in response.text and "SQLite" not in response.text


def test_hidden_history_and_conflict_endpoints_never_cross_boundaries(database):
    first = create(database)
    foreign = create(database, "Foreign confidential fact.", project_id="other-project")
    with Session(database[1]) as db:
        for relation in ["contradicts", "supersedes"]:
            db.add(
                MemoryEdge(
                    id=uuid4(),
                    from_version_id=first.version.id,
                    to_version_id=foreign.version.id,
                    relation=relation,
                )
            )
        db.commit()
    with client_for(database) as client:
        response = client.post(
            "/v1/retrieval/context", json=request(first.id, depth=3, verify_conflicts=True)
        )
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1
        assert str(foreign.id) not in response.text and "confidential" not in response.text


def test_validation_errors_omit_rejected_secrets_and_require_authentication(database):
    saved = create(database)
    with client_for(database) as client:
        rejected = client.post(
            "/v1/retrieval/context",
            json=request(saved.id, conditions={"password": "private-rejected-value"}),
        )
        assert rejected.status_code == 422 and "private-rejected-value" not in rejected.text
        assert (
            client.post("/v1/retrieval/context", json=request(saved.id, limit=11)).status_code
            == 422
        )
        assert (
            client.post(
                "/v1/retrieval/context", json=request(saved.id), headers={"Authorization": ""}
            ).status_code
            == 401
        )


@pytest.mark.parametrize("judgment", ["supports", "contradicts", "insufficient"])
def test_hosted_judge_checks_each_conflict_side_without_resolving_it(
    database, monkeypatch, tmp_path, judgment
):
    first, _ = conflict(database)
    harness = Harness(database)

    def respond(name, value):
        assert name == "JudgmentResponse"
        assert value["claim"] == value["evidence"]
        return {"judgment": judgment}

    replay = HostedReplay(harness, monkeypatch, tmp_path, respond)
    with TestClient(
        create_app(
            harness.settings,
            modules=ModuleGateway(),
            context_verifier=replay.providers.context_verifier,
        ),
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    ) as client:
        response = client.post(
            "/v1/retrieval/context", json=request(first.id, verify_conflicts=True)
        )
        assert response.status_code == 200
        assert {i["evidence_check"] for i in response.json()["items"]} == {judgment}
        assert {i["verification"] for i in response.json()["items"]} == {"uncertain"}
        assert replay.snapshot()["calls"] == {"groq": 2, "cloudflare": 0}


def test_verification_budget_and_no_judge_are_explicit(database):
    seed = create(database, "Primary database fact.")
    peers = [create(database, f"Alternative database fact {i}.") for i in range(4)]
    with Session(database[1]) as db:
        for peer in peers:
            db.add(
                MemoryEdge(
                    id=uuid4(),
                    from_version_id=seed.version.id,
                    to_version_id=peer.version.id,
                    relation="contradicts",
                )
            )
        db.commit()
    calls = []

    class Judge:
        def judge(self, *args):
            calls.append(args)
            return "supports"

    with client_for(database, Judge()) as client:
        result = client.post(
            "/v1/retrieval/context", json=request(seed.id, verify_conflicts=True, limit=10)
        ).json()
        assert len(calls) == 4 and len(result["items"]) == 5
        assert "VERIFICATION_LIMIT_REACHED" in result["warnings"]
        assert all(i["verification"] == "uncertain" for i in result["items"])
    with client_for(database) as client:
        result = client.post(
            "/v1/retrieval/context", json=request(seed.id, verify_conflicts=True)
        ).json()
        assert "VERIFICATION_UNAVAILABLE" in result["warnings"]


def test_developer_global_context_requires_explicit_opt_in(database):
    saved = create(database, scope="developer", project_id=None)
    with client_for(database) as client:
        assert client.post("/v1/retrieval/context", json=request(saved.id)).status_code == 404
        assert (
            client.post(
                "/v1/retrieval/context", json=request(saved.id, include_developer=True)
            ).status_code
            == 200
        )

        assert (
            client.post(
                "/v1/retrieval/context", json=request(saved.id, scope="developer", project_id=None)
            ).status_code
            == 200
        )


def test_forget_during_quota_wait_prevents_the_second_hosted_request(
    database, monkeypatch, tmp_path
):
    first, peer = conflict(database)
    harness = Harness(database)
    replay = HostedReplay(
        harness, monkeypatch, tmp_path, lambda name, value: {"judgment": "supports"}
    )
    gate = replay.backends.context_evidence_judge.client.gate
    advance = gate.sleeper

    def delete_while_waiting(seconds):
        advance(seconds)
        with Session(database[1]) as db:
            MemoryService(db, "developer-a").forget(peer)

    gate.sleeper = delete_while_waiting
    with TestClient(
        create_app(
            harness.settings,
            modules=ModuleGateway(),
            context_verifier=replay.providers.context_verifier,
        ),
        headers={"Authorization": f"Bearer {TEST_TOKEN}"},
    ) as client:
        response = client.post(
            "/v1/retrieval/context", json=request(first.id, verify_conflicts=True)
        )
        assert response.status_code == 409
        assert "PostgreSQL" not in response.text and "SQLite" not in response.text
        assert len(replay.requests) == 1
        assert replay.backends.context_evidence_judge.client.before_call is None


def test_long_history_omits_whole_claim_and_full_inspection_keeps_qualifier(database):
    text = "Database configuration " * 100 + "only applies in the offline environment."
    saved = create(
        database, text, source=source(text), valid_from=datetime.now(UTC) - timedelta(days=2)
    )
    with Session(database[1]) as db:
        MemoryService(db, "developer-a").update(
            saved.id,
            UpdateMemory(
                expected_version=1, content="Use SQLite now.", source=source("Use SQLite now.")
            ),
        )
    with client_for(database) as client:
        response = client.post("/v1/retrieval/context", json=request(saved.id))
        assert response.status_code == 200
        old = response.json()["items"][1]
        assert old["content_omitted"] and old["content"].startswith("[Full claim omitted;")
        assert old["applicable_at_query"] is False
        assert client.get(f"/v1/memories/{saved.id}").json()["history"][0]["content"] == text


def test_oversized_metadata_fails_before_paying_for_verification(database):
    seed = create(database, conditions={str(i) + "界" * 120: "界" * 120 for i in range(20)})

    class Judge:
        def judge(self, *args):
            pytest.fail("Unrepresentable context must fail before any model call")

    with client_for(database, Judge()) as client:
        response = client.post(
            "/v1/retrieval/context",
            json=request(seed.id, conditions=seed.conditions, verify_conflicts=True),
        )
        assert response.status_code == 503
        assert "PostgreSQL" not in response.text

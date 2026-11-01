import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from contextbridge.api import create_app
from contextbridge.config import Settings
from contextbridge.engine import maintenance
from contextbridge.engine.modules import ModuleGateway
from contextbridge.models import CaptureEvent, CaptureJob
from tests.conftest import TEST_TOKEN
from tests.engine.fakes import FakeExtractor, fixture

pytestmark = pytest.mark.integration


@pytest.fixture
def capture_clients(database):
    url, _ = database
    with ExitStack() as stack:

        def make_client(owner="developer-a", project="contextbridge", **changes):
            settings = Settings(
                _env_file=None,
                database_url=url,
                api_token=TEST_TOKEN,
                developer_id=owner,
                capture_project_id=project,
                **changes,
            )
            return stack.enter_context(
                TestClient(create_app(settings), headers={"Authorization": f"Bearer {TEST_TOKEN}"})
            )

        yield make_client


def counts(database):
    with Session(database[1]) as session:
        return (
            session.scalar(select(func.count()).select_from(CaptureEvent)),
            session.scalar(select(func.count()).select_from(CaptureJob)),
        )


def expire_saved_event(database):
    with database[1].begin() as connection:
        connection.execute(
            text(
                "UPDATE capture_events SET received_at = now() - interval '2 days', "
                "expires_at = now() - interval '1 day'"
            )
        )


def test_accepted_work_survives_app_restart_and_replay(database):
    settings = Settings(
        _env_file=None,
        database_url=database[0],
        api_token=TEST_TOKEN,
        developer_id="developer-a",
        capture_project_id="contextbridge",
    )
    extractor = FakeExtractor()
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    payload = fixture("captured-event")
    with TestClient(
        create_app(settings, modules=ModuleGateway(extractor=extractor)), headers=headers
    ) as first:
        accepted = first.post("/v1/interactions", json=payload)
        assert accepted.status_code == 202
        job_id = accepted.json()["job_id"]
        assert accepted.json()["status"] == "accepted"
        assert extractor.calls == []  # Durable acknowledgement never runs provider work inline.
    with TestClient(create_app(settings), headers=headers) as restarted:
        replay = restarted.post("/v1/interactions", json=payload)
        assert replay.json() == {**accepted.json(), "status": "duplicate"}
        status = restarted.get(f"/v1/jobs/{job_id}")
        assert status.status_code == 200
        assert status.json()["status"] == "queued"
        assert status.json()["memory_ids"] == []
        assert "messages" not in status.text and "PostgreSQL" not in status.text
    assert counts(database) == (1, 1)


def test_changed_replay_is_conflict_without_overwrite(capture_clients, database):
    client = capture_clients()
    payload = fixture("captured-event")
    first = client.post("/v1/interactions", json=payload).json()
    payload["messages"][0]["content"] = "Different decision."
    response = client.post("/v1/interactions", json=payload)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "VERSION_CONFLICT"
    assert "Different decision" not in response.text
    with Session(database[1]) as session:
        saved = session.scalar(select(CaptureEvent))
        assert saved.payload == fixture("captured-event")
    assert client.get(f"/v1/jobs/{first['job_id']}").json()["status"] == "queued"


def test_maximum_unicode_content_survives_json_escaping(capture_clients, database):
    payload = fixture("captured-event")
    payload["messages"] = [
        {"message_id": str(i), "role": "user", "content": "🌍" * 8000} for i in range(4)
    ]
    response = capture_clients().post(
        "/v1/interactions",
        content=json.dumps(payload, ensure_ascii=True),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 202
    with Session(database[1]) as session:
        assert session.scalar(select(CaptureEvent)).payload["messages"] == payload["messages"]


def test_replay_does_not_extend_retention_deadline(capture_clients, database):
    client = capture_clients()
    payload = fixture("captured-event")
    client.post("/v1/interactions", json=payload)
    with Session(database[1]) as session:
        deadline = session.scalar(select(CaptureEvent.expires_at))
    payload["occurred_at"] = "2026-10-09T15:30:00+05:30"
    response = client.post("/v1/interactions", json=payload)
    assert response.json()["status"] == "duplicate"
    with Session(database[1]) as session:
        assert session.scalar(select(CaptureEvent.expires_at)) == deadline


def test_authentication_scope_binding_and_owner_isolation(capture_clients, database):
    client = capture_clients()
    payload = fixture("captured-event")
    assert (
        client.post(
            "/v1/interactions", json=payload, headers={"Authorization": "Bearer invalid"}
        ).status_code
        == 401
    )
    accepted = client.post("/v1/interactions", json=payload).json()
    path = f"/v1/jobs/{accepted['job_id']}"
    assert client.get(path, headers={"Authorization": "Bearer invalid"}).status_code == 401
    other_project = capture_clients(project="other-project")
    other_owner = capture_clients(owner="developer-b")
    assert other_project.get(path).status_code == 404
    assert other_owner.get(path).status_code == 404
    assert other_project.post("/v1/interactions", json=payload).status_code == 404
    other_payload = {**payload, "project_id": "other-project"}
    assert other_project.post("/v1/interactions", json=other_payload).status_code == 404
    # Same event ID belongs to an independent namespace for another configured owner.
    independent = other_owner.post("/v1/interactions", json=payload)
    assert independent.status_code == 202
    assert independent.json()["job_id"] != accepted["job_id"]
    assert counts(database) == (2, 2)


def test_developer_scope_requires_opt_in(capture_clients):
    payload = {**fixture("captured-event"), "scope": "developer", "project_id": None}
    assert capture_clients().post("/v1/interactions", json=payload).status_code == 404
    enabled = capture_clients(capture_allow_developer=True)
    response = enabled.post("/v1/interactions", json=payload)
    assert response.status_code == 202
    path = f"/v1/jobs/{response.json()['job_id']}"
    assert enabled.get(path).status_code == 200
    assert capture_clients().get(path).status_code == 404


@pytest.mark.parametrize("field", ["content", "agent", "session", "interaction", "message_id"])
def test_credentials_rejected_in_every_persisted_field(capture_clients, database, field):
    payload = fixture("captured-event")
    value = "password=private-rejected-value"
    if field in {"content", "message_id"}:
        payload["messages"][0][field] = value
    else:
        payload[field] = value
    response = capture_clients().post("/v1/interactions", json=payload)
    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "INVALID_INPUT", "retryable": False}}
    assert "private-rejected-value" not in response.text
    assert counts(database) == (0, 0)


@pytest.mark.parametrize(
    "mutation", ["future", "naive", "oversize", "aggregate", "duplicate", "adapter", "owner"]
)
def test_invalid_events_never_persist(capture_clients, database, mutation):
    payload = fixture("captured-event")
    if mutation == "future":
        payload["occurred_at"] = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    elif mutation == "naive":
        payload["occurred_at"] = "2026-01-01T00:00:00"
    elif mutation == "oversize":
        payload["messages"][0]["content"] = "x" * 8001
    elif mutation == "aggregate":
        payload["messages"] = [
            {"message_id": str(i), "role": "user", "content": "x" * 8000} for i in range(5)
        ]
    elif mutation == "duplicate":
        payload["messages"].append(deepcopy(payload["messages"][0]))
    elif mutation == "adapter":
        payload["capture_method"] = "verified_adapter"
    else:
        payload["developer_id"] = "someone-else"
    response = capture_clients().post("/v1/interactions", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_INPUT"
    assert counts(database) == (0, 0)


def test_atomic_event_job_transaction_on_failed_job_insert(capture_clients, database):
    def reject_job(mapper, connection, target):
        raise SQLAlchemyError("private-db-exception")

    client = capture_clients()
    event.listen(CaptureJob, "before_insert", reject_job)
    try:
        response = client.post("/v1/interactions", json=fixture("captured-event"))
    finally:
        event.remove(CaptureJob, "before_insert", reject_job)
    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "STORAGE_UNAVAILABLE", "retryable": True}}
    assert "private-db-exception" not in response.text
    assert counts(database) == (0, 0)
    assert client.post("/v1/interactions", json=fixture("captured-event")).status_code == 202


@pytest.mark.parametrize("changed", [False, True])
def test_concurrent_event_replays_create_one_job(capture_clients, database, changed):
    clients = [capture_clients(), capture_clients()]
    gate = Barrier(2)
    payloads = [fixture("captured-event"), fixture("captured-event")]
    if changed:
        payloads[1]["messages"][0]["content"] = "A competing payload."

    def ingest(i):
        gate.wait(timeout=10)
        return clients[i].post("/v1/interactions", json=payloads[i])

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(ingest, range(2)))
    if changed:
        assert sorted(response.status_code for response in responses) == [202, 409]
    else:
        assert [response.status_code for response in responses] == [202, 202]
        assert {response.json()["status"] for response in responses} == {"accepted", "duplicate"}
        assert len({response.json()["job_id"] for response in responses}) == 1
    assert counts(database) == (1, 1)


def test_concurrent_quota_is_per_owner_and_replay_works_when_full(capture_clients, database):
    clients = [
        capture_clients(capture_max_buffered_events=1),
        capture_clients(capture_max_buffered_events=1),
    ]
    gate = Barrier(2)
    payloads = [{**fixture("captured-event"), "event_id": str(uuid4())} for _ in range(2)]

    def ingest(i):
        gate.wait(timeout=10)
        return clients[i].post("/v1/interactions", json=payloads[i])

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(ingest, range(2)))
    assert sorted(response.status_code for response in responses) == [202, 503]
    winner = next(i for i, response in enumerate(responses) if response.status_code == 202)
    replay = clients[winner].post("/v1/interactions", json=payloads[winner])
    assert replay.json()["status"] == "duplicate"
    other_project = capture_clients(project="other-project", capture_max_buffered_events=1)
    other_payload = {
        **fixture("captured-event"),
        "event_id": str(uuid4()),
        "project_id": "other-project",
    }
    assert other_project.post("/v1/interactions", json=other_payload).status_code == 503
    assert counts(database) == (1, 1)


def test_expiry_erases_content_and_fingerprint_and_prevents_replay(capture_clients, database):
    client = capture_clients(capture_max_buffered_events=1)
    payload = fixture("captured-event")
    accepted = client.post("/v1/interactions", json=payload).json()
    expire_saved_event(database)
    response = client.get(f"/v1/jobs/{accepted['job_id']}")
    assert response.json()["status"] == "cancelled"
    assert response.json()["reason_codes"] == ["CANCELLED"]
    with Session(database[1]) as session:
        saved = session.scalar(select(CaptureEvent))
        assert saved.payload is None and saved.fingerprint is None
    replay = client.post("/v1/interactions", json=payload)
    assert replay.status_code == 409
    assert replay.json()["detail"]["code"] == "CANCELLED"
    assert (
        client.post("/v1/interactions", json={**payload, "event_id": str(uuid4())}).status_code
        == 202
    )


def test_expiry_is_committed_even_when_replay_returns_error(capture_clients, database):
    client = capture_clients()
    payload = fixture("captured-event")
    client.post("/v1/interactions", json=payload)
    expire_saved_event(database)
    assert client.post("/v1/interactions", json=payload).status_code == 409
    with Session(database[1]) as session:
        assert session.scalar(select(CaptureEvent)).payload is None


def test_expiry_does_not_modify_another_project_or_owner(capture_clients, database):
    payload = fixture("captured-event")
    client = capture_clients()
    client.post("/v1/interactions", json=payload)
    other = capture_clients(project="other-project")
    other.post(
        "/v1/interactions",
        json={**payload, "event_id": str(uuid4()), "project_id": "other-project"},
    )
    owner = capture_clients(owner="developer-b")
    owner.post("/v1/interactions", json=payload)
    expire_saved_event(database)
    client.get(f"/v1/jobs/{uuid4()}")
    with Session(database[1]) as session:
        rows = session.scalars(select(CaptureEvent)).all()
        assert sum(row.payload is None for row in rows) == 1
        assert all(
            row.payload is not None
            for row in rows
            if row.developer_id == "developer-b" or row.project_id == "other-project"
        )


def test_maintenance_expires_idle_events_and_is_repeatable(
    capture_clients, database, monkeypatch, capsys
):
    capture_clients().post("/v1/interactions", json=fixture("captured-event"))
    expire_saved_event(database)
    settings = Settings(
        _env_file=None,
        database_url=database[0],
        api_token=TEST_TOKEN,
        developer_id="developer-a",
        capture_project_id="contextbridge",
    )
    monkeypatch.setattr(maintenance, "Settings", lambda: settings)
    assert maintenance.main() == 0
    assert "Expired capture buffers: 1" in capsys.readouterr().out
    assert maintenance.main() == 0
    assert "Expired capture buffers: 0" in capsys.readouterr().out

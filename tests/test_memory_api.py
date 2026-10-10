from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from contextbridge.models import Memory, MemoryEdge, MemoryVersion
from tests.test_validation import payload

pytestmark = pytest.mark.integration


def save(client, **changes):
    response = client.post("/v1/memories", json=payload(**changes))
    assert response.status_code == 201, response.text
    return response.json()


def search(client, query="PostgreSQL", **changes):
    body = {"scope": "project", "project_id": "contextbridge", "query": query}
    body.update(changes)
    response = client.post("/v1/memories/search", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def replacement(content="Use SQLite.", version=1, **changes):
    value = {"content": content, "expected_version": version, "source": payload()["source"]}
    value.update(changes)
    return value


def test_persists_across_app_restarts_and_agent_sessions(clients):
    first = clients()
    memory = save(first)
    first.close()
    second = clients()
    results = search(second)
    assert [r["id"] for r in results] == [memory["id"]]
    assert results[0]["version"]["source"]["agent"] == "codex"
    assert second.get(f"/v1/memories/{memory['id']}").status_code == 200


def test_project_and_developer_isolation(clients):
    owner = clients()
    memory = save(owner)
    save(owner, project_id="another-project")
    assert [r["id"] for r in search(owner)] == [memory["id"]]
    other_owner = clients("developer-b")
    assert search(other_owner) == []
    path = f"/v1/memories/{memory['id']}"
    assert other_owner.get(path).status_code == 404
    assert other_owner.put(path, json=replacement()).status_code == 404
    assert other_owner.delete(path).status_code == 404


def test_developer_scope_is_opt_in_and_project_ranks_first(client):
    project = save(client)
    global_memory = save(client, scope="developer", project_id=None)
    assert [r["id"] for r in search(client)] == [project["id"]]
    assert [r["id"] for r in search(client, include_developer=True)] == [
        project["id"],
        global_memory["id"],
    ]
    assert [r["id"] for r in search(client, scope="developer", project_id=None)] == [
        global_memory["id"]
    ]


def test_updates_preserve_history_and_retrieve_requested_time(client):
    old_time = datetime.now(UTC) - timedelta(days=2)
    new_time = old_time + timedelta(days=1)
    memory = save(client, valid_from=old_time.isoformat())
    response = client.put(
        f"/v1/memories/{memory['id']}",
        json=replacement(valid_from=new_time.isoformat()),
    )
    assert response.status_code == 200, response.text
    assert response.json()["current_version"] == 2
    assert search(client) == []
    assert search(client, "SQLite")[0]["id"] == memory["id"]
    historical = search(client, as_of=(old_time + timedelta(hours=1)).isoformat())
    assert historical[0]["version"]["status"] == "SUPERSEDED"
    assert search(client, "SQLite", as_of=new_time.isoformat())[0]["version"]["number"] == 2
    detail = client.get(f"/v1/memories/{memory['id']}").json()
    assert len(detail["history"]) == 2
    assert detail["history"][0]["valid_to"] == response.json()["version"]["valid_from"]
    assert detail["edges"][0]["relation"] == "supersedes"
    assert detail["edges"][0]["to_version_id"] == memory["version"]["id"]


def test_stale_update_and_backdated_update_do_not_modify_history(client):
    memory = save(client, valid_from="2026-01-02T00:00:00Z")
    path = f"/v1/memories/{memory['id']}"
    assert client.put(path, json=replacement(valid_from="2026-01-01T00:00:00Z")).status_code == 422
    assert client.put(path, json=replacement()).status_code == 200
    assert client.put(path, json=replacement("Use MongoDB.")).status_code == 409
    detail = client.get(path).json()
    assert len(detail["history"]) == 2
    assert detail["memory"]["version"]["content"] == "Use SQLite."


def test_concurrent_updates_allow_only_one_winner(client):
    memory = save(client)
    path = f"/v1/memories/{memory['id']}"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda content: client.put(path, json=replacement(content)).status_code,
                ["Use SQLite.", "Use MongoDB."],
            )
        )
    assert sorted(results) == [200, 409]
    assert len(client.get(path).json()["history"]) == 2


def test_create_retries_are_idempotent_and_mismatched_retry_conflicts(client):
    value = payload()
    first = client.post("/v1/memories", json=value)
    second = client.post("/v1/memories", json=value)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    value["content"] = "Different content"
    assert client.post("/v1/memories", json=value).status_code == 409
    assert len(search(client)) == 1


def test_concurrent_create_retries_store_one_record(client):
    value = payload()
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: client.post("/v1/memories", json=value), range(2)))
    assert all(r.status_code == 201 for r in responses)
    assert responses[0].json()["id"] == responses[1].json()["id"]
    assert len(search(client)) == 1


def test_conditions_coexist_and_unconditional_memories_remain_applicable(client):
    production = save(client, conditions={"environment": "production"})
    tests = save(client, content="Use SQLite.", conditions={"environment": "test"})
    general = save(client, content="A database decision applies to each environment.")
    assert search(client) == []  # The environment has not been specified.
    assert search(client, conditions={"environment": "test"}) == []
    assert search(client, "SQLite", conditions={"environment": "test"})[0]["id"] == tests["id"]
    assert search(client, conditions={"environment": "production"})[0]["id"] == production["id"]
    assert search(client, "database", conditions={"environment": "test"})[0]["id"] == general["id"]


def test_full_text_exact_identifiers_limits_and_literal_wildcards(client):
    for i in range(5):
        save(client, content=f"Database choice {i}: PostgreSQL.")
    assert len(search(client, "database choice")) == 3
    assert len(search(client, "database choice", limit=5)) == 5
    name = save(client, content="Authentication lives in auth/session.ts.")
    assert search(client, "auth/session.ts")[0]["id"] == name["id"]
    assert search(client, "%") == []
    assert search(client, "_") == []
    assert search(client, "xyz' OR 1=1 --") == []


def test_forget_removes_all_versions_evidence_and_relationships(client, database):
    memory = save(client)
    path = f"/v1/memories/{memory['id']}"
    assert client.put(path, json=replacement()).status_code == 200
    assert client.delete(path).status_code == 204
    assert client.get(path).status_code == 404
    assert search(client, "SQLite") == []
    _, engine = database
    with Session(engine) as session:
        for model in (Memory, MemoryVersion, MemoryEdge):
            assert session.scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.parametrize("field", ["content", "evidence", "agent", "conditions"])
def test_credentials_are_rejected_in_every_persisted_field(client, field):
    secret = "sk-proj-abcdefghijklmnopqrstuvwx"
    value = payload()
    if field == "content":
        value[field] = secret
    elif field == "conditions":
        value[field] = {"api_key": secret}
    else:
        value["source"][field] = secret
    response = client.post("/v1/memories", json=value)
    assert response.status_code == 422
    assert secret not in response.text
    assert search(client) == []


def test_secret_in_update_preserves_previous_state(client):
    memory = save(client)
    path = f"/v1/memories/{memory['id']}"
    assert client.put(path, json=replacement("password=secret-value")).status_code == 422
    assert len(client.get(path).json()["history"]) == 1


def test_escaped_json_evidence_and_short_condition_credentials_are_rejected(client):
    value = payload()
    value["source"]["evidence"] = '{"password": "private-value"}'
    assert client.post("/v1/memories", json=value).status_code == 422
    value = payload(conditions={"password": "tiny"})
    assert client.post("/v1/memories", json=value).status_code == 422
    assert search(client) == []


def test_retries_ignore_condition_key_order(client):
    value = payload(conditions={"environment": "test", "version": "v1"})
    first = client.post("/v1/memories", json=value)
    value["conditions"] = {"version": "v1", "environment": "test"}
    replay = client.post("/v1/memories", json=value)
    assert first.status_code == replay.status_code == 201
    assert first.json()["id"] == replay.json()["id"]


def test_invalid_inputs_are_not_echoed(client):
    value = payload()
    value["developer_id"] = "sk-proj-supersecretabcdefghijkl"
    response = client.post("/v1/memories", json=value)
    assert response.status_code == 422
    assert value["developer_id"] not in response.text
    assert client.get(f"/v1/memories/{uuid4()}").status_code == 404


@pytest.mark.parametrize("authorization", [None, "Bearer wrong-token", "Basic abcdef"])
def test_memory_operations_require_authentication(client, authorization):
    client.headers.pop("Authorization")
    if authorization:
        client.headers["Authorization"] = authorization
    assert client.post("/v1/memories", json=payload()).status_code == 401
    assert (
        client.post(
            "/v1/memories/search", json={"scope": "developer", "query": "database"}
        ).status_code
        == 401
    )
    path = f"/v1/memories/{uuid4()}"
    assert client.get(path).status_code == 401
    assert client.put(path, json=replacement()).status_code == 401
    assert client.delete(path).status_code == 401
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 401


def test_readiness_checks_database_schema(client):
    assert client.get("/health/ready").status_code == 200

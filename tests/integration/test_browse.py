from datetime import UTC, datetime, timedelta

import pytest

from tests.integration.write_fakes import Harness
from tests.test_validation import payload

pytestmark = pytest.mark.integration


def browse_query(**changes):
    return {"schema_version": 1, "scope": "project", "project_id": "contextbridge", **changes}


def create(client, content="A useful decision.", **changes):
    response = client.post("/v1/memories", json=payload(content=content, **changes))
    assert response.status_code == 201
    return response.json()


def test_browse_filters_before_limits_and_exposes_legacy_records(database):
    harness = Harness(database)
    with harness.client() as client:
        unrelated = create(client, project_id="other-project")
        conditional = create(client, conditions={"environment": "production"})
        global_memory = create(client, scope="developer", project_id=None)
        target = create(client)
        response = client.post("/v1/inspection/browse", json=browse_query(limit=1))
        assert response.status_code == 200
        result = response.json()
        assert [item["memory"]["id"] for item in result["items"]] == [target["id"]]
        assert result["next_cursor"] is None
        assert result["items"][0]["confidence"] is None
        assert result["items"][0]["decision_state"] == "clear"
        matched = client.post(
            "/v1/inspection/browse", json=browse_query(conditions={"environment": "production"})
        ).json()
        assert {item["memory"]["id"] for item in matched["items"]} == {
            target["id"],
            conditional["id"],
        }
        developer = client.post(
            "/v1/inspection/browse", json={"schema_version": 1, "scope": "developer"}
        ).json()
        assert [item["memory"]["id"] for item in developer["items"]] == [global_memory["id"]]
        assert unrelated["id"] not in {item["memory"]["id"] for item in matched["items"]}
    with Harness(database, owner="unrelated-owner").client() as client:
        assert client.post("/v1/inspection/browse", json=browse_query()).json()["items"] == []


def test_browse_paginates_stably_with_one_resolved_time(database):
    harness = Harness(database)
    with harness.client() as client:
        created = [create(client, content=f"Decision {i}.") for i in range(3)]
        created.sort(key=lambda memory: memory["id"])
        first = client.post("/v1/inspection/browse", json=browse_query(limit=1)).json()
        target = created[1]
        assert first["items"][0]["memory"]["id"] == created[0]["id"]
        update = {
            "expected_version": 1,
            "content": "A new decision.",
            "source": target["version"]["source"],
        }
        assert client.put(f"/v1/memories/{target['id']}", json=update).status_code == 200
        second = client.post(
            "/v1/inspection/browse", json=browse_query(limit=1, cursor=first["next_cursor"])
        ).json()
        assert second["items"][0]["memory"]["id"] == target["id"]
        assert second["items"][0]["memory"]["version"]["number"] == 1
        assert second["items"][0]["memory"]["version"]["status"] == "SUPERSEDED"
        third = client.post(
            "/v1/inspection/browse", json=browse_query(limit=1, cursor=second["next_cursor"])
        ).json()
        assert third["items"][0]["memory"]["id"] == created[2]["id"]
        assert third["next_cursor"] is None


def test_cursor_is_bound_to_owner_filters_and_signature(database):
    harness = Harness(database)
    with harness.client() as client:
        for i in range(2):
            create(client, content=f"Decision {i}.")
        cursor = client.post("/v1/inspection/browse", json=browse_query(limit=1)).json()[
            "next_cursor"
        ]
        for query in [
            browse_query(cursor="invalid"),
            browse_query(cursor=cursor + "x"),
            browse_query(cursor=cursor, project_id="other-project"),
            browse_query(cursor=cursor, conditions={"environment": "production"}),
            browse_query(cursor=cursor, as_of="2026-01-01T00:00:00Z"),
        ]:
            response = client.post("/v1/inspection/browse", json=query)
            assert (
                response.status_code == 422 and response.json()["detail"]["code"] == "INVALID_INPUT"
            )
    with Harness(database, owner="unrelated-owner").client() as client:
        response = client.post("/v1/inspection/browse", json=browse_query(cursor=cursor))
        assert response.status_code == 422 and "Decision" not in response.text


def test_historical_browse_obeys_effective_intervals(database):
    harness = Harness(database)
    start = datetime.now(UTC) - timedelta(days=3)
    change = start + timedelta(days=1)
    with harness.client() as client:
        saved = create(client, valid_from=start.isoformat())
        update = {
            "expected_version": 1,
            "content": "Changed decision.",
            "source": saved["version"]["source"],
            "valid_from": change.isoformat(),
        }
        assert client.put(f"/v1/memories/{saved['id']}", json=update).status_code == 200
        for instant, number in [(start - timedelta(seconds=1), None), (start, 1), (change, 2)]:
            items = client.post(
                "/v1/inspection/browse", json=browse_query(as_of=instant.isoformat())
            ).json()["items"]
            assert [item["memory"]["version"]["number"] for item in items] == (
                [] if number is None else [number]
            )


def test_browse_authentication_and_safe_validation(database):
    with Harness(database).client() as client:
        assert (
            client.post(
                "/v1/inspection/browse",
                json=browse_query(),
                headers={"Authorization": "Bearer invalid"},
            ).status_code
            == 401
        )
        for query in [
            browse_query(limit=101),
            browse_query(project_id=None),
            browse_query(cursor="x" * 2049),
            browse_query(conditions={"password": "private-value"}),
        ]:
            response = client.post("/v1/inspection/browse", json=query)
            assert response.status_code == 422 and "private-value" not in response.text


def test_fixture_browse_shape_matches_agreed_shared_types():
    from contextbridge.contracts import BrowseQuery, BrowseResult
    from tests.engine.fakes import fixture

    BrowseQuery.model_validate(fixture("browse-query"))
    BrowseResult.model_validate(fixture("browse-result"))

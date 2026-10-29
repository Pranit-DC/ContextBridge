"""Effective-time and condition behavior across writes, browse, and both search APIs."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from contextbridge.retrieval import RetrievalConfig, Retriever
from contextbridge.retrieval.verifier import EvidenceVerifier
from tests.integration.retrieval_fakes import create, query
from tests.integration.test_conflict_comparison import resolver, save, snapshot
from tests.integration.test_retrieval_api import api
from tests.integration.write_fakes import Harness
from tests.test_validation import payload

pytestmark = pytest.mark.integration


def read_versions(client, endpoint, **changes):
    request = query(limit=20, **changes)
    if endpoint == "browse":
        request.pop("query")
        path = "/v1/inspection/browse"
    elif endpoint == "legacy":
        request.pop("schema_version")
        path = "/v1/memories/search"
    else:
        path = "/v1/retrieval/search"
    response = client.post(path, json=request)
    assert response.status_code == 200, response.text
    body = response.json()
    if endpoint == "retrieval":
        return {card["memory_id"]: card["version_number"] for card in body["cards"]}
    items = body["items"] if endpoint == "browse" else body
    memories = [item["memory"] for item in items] if endpoint == "browse" else items
    return {memory["id"]: memory["version"]["number"] for memory in memories}


@pytest.mark.parametrize("endpoint", ["browse", "legacy", "retrieval"])
def test_half_open_intervals_and_timezone_equivalence_across_read_paths(database, endpoint):
    start = datetime.now(UTC) - timedelta(days=3)
    change = start + timedelta(days=1)
    saved = create(database, valid_from=start.isoformat(), conditions={"environment": "production"})
    create(database, project_id="other-project", valid_from=start.isoformat())
    create(database, owner="other-owner", valid_from=start.isoformat())
    with api(database, Retriever()) as client:
        corrected = client.put(
            f"/v1/memories/{saved.id}",
            json={
                "expected_version": 1,
                "content": "Use SQLite database.",
                "source": saved.version.source.model_dump(mode="json"),
                "valid_from": change.isoformat(),
            },
        )
        assert corrected.status_code == 200
        for instant, number in [
            (start - timedelta(microseconds=1), None),
            (start, 1),
            (change - timedelta(microseconds=1), 1),
            (change, 2),
            (change + timedelta(microseconds=1), 2),
        ]:
            for offset in [UTC, timezone(timedelta(hours=5, minutes=30))]:
                found = read_versions(
                    client,
                    endpoint,
                    as_of=instant.astimezone(offset).isoformat(),
                    conditions={"environment": "production"},
                )
                assert found == ({} if number is None else {str(saved.id): number})
        assert read_versions(client, endpoint, conditions={"environment": "production"}) == {
            str(saved.id): 2
        }
        history = client.get(f"/v1/memories/{saved.id}").json()["history"]
        assert history[0]["valid_to"] == history[1]["valid_from"]
        assert [version["status"] for version in history] == ["SUPERSEDED", "ACTIVE"]
        assert history[0]["source"] == saved.version.source.model_dump(mode="json")


@pytest.mark.parametrize("endpoint", ["browse", "legacy", "retrieval"])
def test_condition_conjunction_and_environment_specific_correction_preserve_history(
    database, endpoint
):
    start = datetime.now(UTC) - timedelta(days=3)
    change = start + timedelta(days=1)
    general = create(
        database, content="Database documentation is in docs/.", valid_from=start.isoformat()
    )
    production = create(
        database,
        conditions={"environment": "production", "region": "india"},
        valid_from=start.isoformat(),
    )
    staging = create(
        database,
        content="Use SQLite database.",
        conditions={"environment": "staging"},
        valid_from=start.isoformat(),
    )
    with api(database, Retriever()) as client:
        response = client.put(
            f"/v1/memories/{production.id}",
            json={
                "expected_version": 1,
                "content": "Use MySQL database.",
                "valid_from": change.isoformat(),
                "source": production.version.source.model_dump(mode="json"),
            },
        )
        assert response.status_code == 200
        for instant, version in [(change - timedelta(microseconds=1), 1), (change, 2), (None, 2)]:
            for conditions, extra in [
                ({}, {}),
                ({"environment": "production"}, {}),
                ({"environment": "production", "region": "elsewhere"}, {}),
                ({"environment": "production", "region": "india"}, {str(production.id): version}),
                (
                    {"environment": "production", "region": "india", "release": "v1"},
                    {str(production.id): version},
                ),
                ({"environment": "staging"}, {str(staging.id): 1}),
            ]:
                found = read_versions(
                    client,
                    endpoint,
                    conditions=conditions,
                    as_of=instant.isoformat() if instant else None,
                )
                assert found == {str(general.id): 1, **extra}
        inspected = client.get(f"/v1/memories/{staging.id}").json()
        assert len(inspected["history"]) == 1 and inspected["edges"] == []


@pytest.mark.parametrize(
    "transition", ["uncertain", "multiple_corrections", "equal_time", "out_of_order"]
)
def test_ambiguous_transitions_never_rewrite_the_current_or_historical_state(database, transition):
    harness = Harness(database, formation_enabled=True)
    start = datetime.now(UTC) - timedelta(days=3)
    original = "Use PostgreSQL database."
    save(harness, original, time=start)
    relations = {original: "uncertain" if transition == "uncertain" else "correction"}
    if transition == "multiple_corrections":
        resolver(harness, {original: "unrelated"})
        other = "Use MySQL database."
        save(harness, other, time=start)
        relations[other] = "correction"
    resolver(harness, relations)
    before = snapshot(database)
    effective = start + timedelta(days=1)
    if transition in {"equal_time", "out_of_order"}:
        effective = start if transition == "equal_time" else start - timedelta(microseconds=1)
    job, _, _ = harness.enqueue("Use SQLite database.", time=effective)
    result = harness.process(job)
    assert result.status == "deferred" and result.memory_ids == []
    assert result.reason_codes == [
        "AMBIGUOUS_TIME"
        if transition in {"equal_time", "out_of_order"}
        else "INSUFFICIENT_EVIDENCE"
    ]
    assert snapshot(database) == before
    assert harness.process(job).status == "deferred" and snapshot(database) == before


def test_unresolved_conflict_stays_visible_and_uncertain_in_current_and_historical_cards(database):
    harness = Harness(database, formation_enabled=True)
    start = datetime.now(UTC) - timedelta(days=3)
    change = start + timedelta(days=1)
    original = "Use PostgreSQL database."
    first = save(harness, original, time=start)
    resolver(harness, {original: "contradiction"})
    second = save(harness, "Do not use PostgreSQL database.", time=change)

    class ForbiddenJudge:
        def judge(self, claim, evidence):
            pytest.fail("A contested group must remain uncertain without choosing a winner")

    with api(database, Retriever(RetrievalConfig(max_verifications=3))) as client:
        client.app.state.verifier = EvidenceVerifier(ForbiddenJudge())
        for instant, expected in [
            (start, {str(first)}),
            (change, {str(first), str(second)}),
            (None, {str(first), str(second)}),
        ]:
            response = client.post(
                "/v1/retrieval/search", json=query(as_of=instant.isoformat() if instant else None)
            )
            assert response.status_code == 200
            cards = response.json()["cards"]
            assert {card["memory_id"] for card in cards} == expected
            assert {card["decision_state"] for card in cards} == {"contested"}
            assert {card["verification"] for card in cards} == {"uncertain"}


def test_future_and_out_of_order_explicit_writes_leave_no_partial_changes(database):
    start = datetime.now(UTC) - timedelta(days=3)
    saved = create(database, valid_from=start.isoformat())
    before = snapshot(database)
    with api(database, Retriever()) as client:
        for instant in [
            start - timedelta(microseconds=1),
            start,
            datetime.now(UTC) + timedelta(days=1),
        ]:
            response = client.put(
                f"/v1/memories/{saved.id}",
                json={
                    "expected_version": 1,
                    "content": "Use SQLite database.",
                    "valid_from": instant.isoformat(),
                    "source": saved.version.source.model_dump(mode="json"),
                },
            )
            assert response.status_code == 422
            assert snapshot(database) == before
        response = client.post(
            "/v1/memories",
            json=payload(valid_from=(datetime.now(UTC) + timedelta(days=1)).isoformat()),
        )
        assert response.status_code == 422 and snapshot(database) == before


def test_future_effective_candidate_is_rejected_without_rewriting_existing_memory(database):
    harness = Harness(database)
    save(harness, "Use PostgreSQL database.")
    before = snapshot(database)
    job, candidate, event = harness.enqueue("Use SQLite database.")
    candidate["valid_from"] = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    harness.extractor.outputs[event["event_id"]] = [candidate]
    result = harness.process(job)
    assert result.status == "failed" and result.reason_codes == ["INVALID_PROVIDER_OUTPUT"]
    assert snapshot(database) == before

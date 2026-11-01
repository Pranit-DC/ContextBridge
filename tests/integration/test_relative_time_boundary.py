from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from contextbridge.models import Memory
from tests.integration.write_fakes import Harness


def test_sqlite_yesterday_with_date_precision_defers_in_v1_pipeline(database):
    harness = Harness(database, capture_source_timezone="Asia/Kolkata")
    job, _, _ = harness.enqueue("We switched to SQLite yesterday.")
    result = harness.process(job)
    assert result.status == "deferred" and result.reason_codes == ["AMBIGUOUS_TIME"]
    with Session(database[1]) as db:
        assert db.scalar(select(func.count()).select_from(Memory)) == 0


def test_ambiguous_date_does_not_block_other_supported_claims_in_same_event(database):
    harness = Harness(database, capture_source_timezone="Asia/Kolkata")
    job, candidate, event = harness.enqueue("Switched SQLite yesterday. Pin Python 3.12.")
    clear = deepcopy(candidate)
    clear.update(candidate_id=str(uuid4()), content="Pin Python 3.12.", claim_key=None)
    clear["source"]["evidence"] = clear["content"]
    harness.extractor.outputs[event["event_id"]] = [candidate, clear]
    result = harness.process(job)
    assert result.status == "deferred" and "AMBIGUOUS_TIME" in result.reason_codes
    assert len(result.memory_ids) == 1
    assert harness.process(job).memory_ids == result.memory_ids


def test_exact_relative_time_preserves_source_units_identifiers_and_conditions(database):
    harness = Harness(database, capture_source_timezone="UTC")
    timestamp = datetime.now(UTC).replace(hour=12, minute=0, second=0, microsecond=0) - timedelta(
        days=2
    )
    job, _, _ = harness.enqueue(
        "Pin db_v1.sqlite to 64 MB; switched yesterday at 09:30.",
        time=timestamp,
        conditions={"version": "V1"},
    )
    result = harness.process(job)
    assert result.status == "succeeded"
    with harness.client() as client:
        memory = client.get(f"/v1/memories/{result.memory_ids[0]}").json()["memory"]
        assert memory["conditions"] == {"version": "V1"}
        assert (
            "64 MB" in memory["version"]["content"]
            and "db_v1.sqlite" in memory["version"]["content"]
        )
        expected = (timestamp - timedelta(days=1)).replace(hour=9, minute=30)
        assert (
            datetime.fromisoformat(memory["version"]["valid_from"].replace("Z", "+00:00"))
            == expected
        )

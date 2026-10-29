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

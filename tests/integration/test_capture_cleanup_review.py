from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from contextbridge.models import CaptureJob
from contextbridge.persistence.capture_cleanup import cancel_capture_jobs
from tests.background.test_work import work_id
from tests.integration.test_session_groups import enqueue, setup
from tests.integration.write_fakes import Harness


def test_large_cancellation_selection_respects_postgresql_parameter_limit(database):
    harness, _, worker = setup(database, capture_group_max_events=2)
    first, _ = enqueue(harness)
    second, _ = enqueue(harness)
    assert worker.claim(work_id(database, first)) is not None
    foreign = Harness(database, owner="developer-b")
    foreign_job, _, _ = foreign.enqueue()
    # The configured buffer can contain 100,000 captures; psycopg allows 65,535 bind parameters.
    identifiers = [uuid4() for _ in range(65_536)] + [first]
    with Session(database[1]) as db:
        cancel_capture_jobs(db, identifiers)
        db.commit()
        assert db.get(CaptureJob, first).status == "cancelled"
        assert db.get(CaptureJob, second).status == "cancelled"
        assert db.get(CaptureJob, UUID(foreign_job)).status == "queued"

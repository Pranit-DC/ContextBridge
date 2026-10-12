from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from contextbridge.config import Settings
from contextbridge.db import make_session_factory
from contextbridge.engine.errors import ModuleError
from contextbridge.formation.providers.chat import Observation
from contextbridge.models import ProviderQuota
from contextbridge.persistence.provider_quota import AccountGate
from tests.conftest import TEST_TOKEN
from tests.formation.test_groq_provider import settings as formation_settings

pytestmark = pytest.mark.integration


def gate(database, clock, **limits):
    configuration = Settings(
        _env_file=None, database_url=database[0], api_token=TEST_TOKEN, **limits
    )
    return AccountGate(
        make_session_factory(database[1]),
        configuration,
        formation_settings(),
        clock=lambda: clock[0],
        sleeper=lambda delay: clock.__setitem__(0, clock[0] + timedelta(seconds=delay)),
    )


def test_account_serializes_independent_clients_and_keeps_crash_reservation(database):
    clock = [datetime.now(UTC)]
    first, second = gate(database, clock), gate(database, clock)
    first.pending_tokens = second.pending_tokens = 4000
    first.wait()
    with pytest.raises(ModuleError, match="PROVIDER_UNAVAILABLE"):
        second.wait()
    # Simulate disconnect/process death before observing usage: committed charge survives.
    connection = first.session.get_bind()
    first.session.close()
    connection.invalidate()
    connection.close()
    first.session = None
    second.wait()
    second.observe(None)
    with Session(database[1]) as db:
        row = db.get(ProviderQuota, first.account)
        assert row.day_tokens == 8000
        assert sum(entry[1] for entry in row.window) == 8000
        assert formation_settings().api_key.get_secret_value() not in str(row.window)
    third = gate(database, clock)
    third.pending_tokens = 1
    with pytest.raises(ModuleError, match="PROVIDER_UNAVAILABLE"):
        third.wait()


def test_usage_refunds_reservation_and_shared_failure_blocks_new_job(database):
    clock = [datetime.now(UTC)]
    first = gate(database, clock)
    first.pending_tokens = 7000
    first.wait()
    first.observe(Observation("fixture", 0.1, 100, 50, None, 200))
    with Session(database[1]) as db:
        assert db.get(ProviderQuota, first.account).day_tokens == 150
    failed = gate(database, clock)
    failed.pending_tokens = 1000
    failed.wait()
    failed.failure = True
    failed.observe(Observation(None, 0.1, None, None, None, 429))
    another = gate(database, clock)
    another.pending_tokens = 100
    with pytest.raises(ModuleError, match="PROVIDER_UNAVAILABLE"):
        another.wait()
    clock[0] += timedelta(seconds=62)
    another.wait()
    another.observe(None)


def test_daily_limit_resets_and_bad_reservations_do_not_call_provider(database):
    clock = [datetime.now(UTC)]
    first = gate(database, clock, formation_tokens_per_day=500)
    first.pending_tokens = 500
    first.wait()
    first.observe(None)
    clock[0] += timedelta(seconds=62)
    second = gate(database, clock, formation_tokens_per_day=500)
    second.pending_tokens = 1
    with pytest.raises(ModuleError):
        second.wait()
    clock[0] += timedelta(days=1)
    second.wait()
    second.observe(None)
    second.pending_tokens = 8001
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        second.wait()

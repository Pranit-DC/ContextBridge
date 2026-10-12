"""Serialize hosted requests across API/worker processes using numeric database state.

Reserve BEFORE the network call in a separate committed transaction. A process crash keeps
the conservative reservation. An advisory lock serializes requests and is released by PostgreSQL
on disconnect; it is independent of memory-owner locks. Waiting is bounded, never under an
owner lock. Provider limits remain authoritative and can be lower than these local limits.
"""

import hashlib
import time
from datetime import UTC, datetime, timedelta
from threading import Lock

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from contextbridge.engine.errors import ModuleError
from contextbridge.models import ProviderQuota


class AccountGate:
    def __init__(self, sessions, settings, formation, *, clock=None, sleeper=time.sleep):
        self.sessions = sessions
        self.limit = settings.formation_tokens_per_minute
        self.budget = settings.formation_tokens_per_day
        self.clock = clock or (lambda: datetime.now(UTC))
        self.sleeper = sleeper
        secret = formation.api_key.get_secret_value()
        self.account = hashlib.sha256((formation.base_url + "\0" + secret).encode()).hexdigest()
        self.lock_id = int(self.account[:16], 16) - 2**63
        self.lock = Lock()
        self.pending_tokens = 0
        self.failure = None
        self.estimator = None
        self.active = None
        self.session = None

    def wait(self):
        if self.failure is not None:
            raise ModuleError("PROVIDER_UNAVAILABLE", retryable=self.failure)
        amount = self.pending_tokens
        if type(amount) is not int or amount < 1 or amount > self.limit:
            raise ModuleError("INVALID_INPUT")
        with self.sessions() as probe:
            connection = probe.get_bind().connect()
        db = Session(bind=connection, expire_on_commit=False)
        self.session = db
        acquired = False
        try:
            # Session advisory locks survive commits of the numeric reservation.
            acquired = db.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": self.lock_id})
            if not acquired:
                raise ModuleError("PROVIDER_UNAVAILABLE", retryable=True)
            now = self.clock()
            db.execute(
                insert(ProviderQuota)
                .values(
                    account_hash=self.account,
                    window=[],
                    day_started=now,
                    day_tokens=0,
                    next_at=now,
                    blocked_until=now,
                )
                .on_conflict_do_nothing()
            )
            row = db.get(ProviderQuota, self.account)
            if row.blocked_until > now:
                raise ModuleError("PROVIDER_UNAVAILABLE", retryable=True)
            delay = max(0, (row.next_at - now).total_seconds())
            if delay > 3.2:
                raise ModuleError("PROVIDER_UNAVAILABLE", retryable=True)
            if delay:
                self.sleeper(delay)
                now = self.clock()
            window = [entry for entry in row.window if now.timestamp() - entry[0] < 61]
            if now - row.day_started >= timedelta(days=1):
                row.day_started, row.day_tokens = now, 0
            if (
                sum(entry[1] for entry in window) + amount > self.limit
                or row.day_tokens + amount > self.budget
            ):
                raise ModuleError("PROVIDER_UNAVAILABLE", retryable=True)
            self.active = [now.timestamp(), amount]
            row.window = [*window, self.active]
            row.day_tokens += amount
            row.next_at = now + timedelta(seconds=3.1)
            db.commit()
        except Exception:
            self.release(db, acquired=acquired)
            self.session = None
            raise

    def release(self, db, *, acquired=True):
        connection = db.get_bind()
        try:
            db.rollback()
            if acquired:
                db.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": self.lock_id})
        except Exception:
            # An unlock failure must discard the backend, never return a locked pooled session.
            connection.invalidate()
        finally:
            db.close()
            connection.close()

    def observe(self, observation):
        db, self.session = self.session, None
        if db is None:
            return
        try:
            row = db.scalar(select(ProviderQuota).where(ProviderQuota.account_hash == self.account))
            values = [
                getattr(observation, name, None) for name in ("input_tokens", "output_tokens")
            ]
            if all(type(value) is int and 0 <= value <= 1_000_000_000 for value in values):
                actual = sum(values)
                window = list(row.window)
                window[-1] = [self.active[0], actual]
                row.window = window
                row.day_tokens += actual - self.active[1]
            if self.failure is not None:
                row.blocked_until = self.clock() + timedelta(seconds=61 if self.failure else 900)
            db.commit()
        finally:
            # Explicit unlock before returning this pooled connection.
            self.release(db)
            self.active = None

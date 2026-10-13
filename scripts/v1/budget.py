"""A crash-safe, cross-process request ceiling for this synthetic demo only."""

import contextlib
import os
import sqlite3
import time
from pathlib import Path

import httpx

from contextbridge.engine.errors import ModuleError

LIMITS = {"groq": 40, "cloudflare": 20}


@contextlib.contextmanager
def exclusive(path):
    with Path(str(path) + ".lock").open("a+b") as file:
        if os.name == "nt":
            import msvcrt

            file.seek(0)
            file.write(b"0")
            file.flush()
            file.seek(0)
            msvcrt.locking(file.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                file.seek(0)
                msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(file.fileno(), fcntl.LOCK_UN)


class Ledger:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with exclusive(self.path), self.db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS budget "
                "(provider TEXT PRIMARY KEY, calls INTEGER NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS state "
                "(id INTEGER PRIMARY KEY, stopped INTEGER NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS requests "
                "(id INTEGER PRIMARY KEY, provider TEXT, status INTEGER, latency_ms INTEGER)"
            )
            for provider in LIMITS:
                db.execute("INSERT OR IGNORE INTO budget VALUES (?, 0)", (provider,))
            db.execute("INSERT OR IGNORE INTO state VALUES (1, 0)")

    @contextlib.contextmanager
    def db(self):
        with contextlib.closing(sqlite3.connect(self.path, timeout=120)) as db, db:
            yield db

    def snapshot(self):
        with self.db() as db:
            return {
                "calls": dict(db.execute("SELECT provider, calls FROM budget")),
                "stopped": bool(db.execute("SELECT stopped FROM state WHERE id=1").fetchone()[0]),
            }

    def stop(self):
        with self.db() as db:
            db.execute("UPDATE state SET stopped=1 WHERE id=1")

    def reserve(self, provider):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT stopped FROM state WHERE id=1").fetchone()[0]:
                raise ModuleError("CANCELLED")
            count = db.execute("SELECT calls FROM budget WHERE provider=?", (provider,)).fetchone()[
                0
            ]
            if count >= LIMITS[provider]:
                db.execute("UPDATE state SET stopped=1 WHERE id=1")
                db.commit()
                raise ModuleError("CANCELLED")
            db.execute("UPDATE budget SET calls=calls+1 WHERE provider=?", (provider,))
            row = db.execute("INSERT INTO requests(provider) VALUES (?)", (provider,))
            # Count survives a process crash before/during network execution.
            db.commit()
            return row.lastrowid

    def observed(self, identifier, status, elapsed):
        with self.db() as db:
            db.execute(
                "UPDATE requests SET status=?, latency_ms=? WHERE id=?",
                (status, int(elapsed * 1000), identifier),
            )


class BudgetTransport(httpx.BaseTransport):
    def __init__(self, ledger, provider, *, transport=None):
        if provider not in LIMITS:
            raise ValueError("INVALID_DEMO_PROVIDER")
        self.ledger, self.provider = Ledger(ledger), provider
        self.transport = transport

    def handle_request(self, request):
        with exclusive(self.ledger.path):
            identifier = self.ledger.reserve(self.provider)
            started = time.monotonic()
            transport = self.transport or httpx.HTTPTransport(retries=0)
            response = None
            try:
                response = transport.handle_request(request)
                raw = bytearray()
                chunks = [response.content] if response.is_stream_consumed else response.iter_raw()
                deadline = min(120, request.extensions.get("timeout", {}).get("read", 30) or 30)
                for chunk in chunks:
                    if len(raw) + len(chunk) > 2_097_152 or time.monotonic() - started >= deadline:
                        raise ModuleError("INVALID_PROVIDER_OUTPUT")
                    raw.extend(chunk)
                response.close()
                self.ledger.observed(identifier, response.status_code, time.monotonic() - started)
                if response.status_code != 200:
                    self.ledger.stop()
                return httpx.Response(
                    response.status_code,
                    headers=response.headers,
                    content=bytes(raw),
                    request=request,
                )
            except Exception:
                self.ledger.stop()
                self.ledger.observed(identifier, None, time.monotonic() - started)
                raise ModuleError("PROVIDER_UNAVAILABLE", retryable=False) from None
            finally:
                if response is not None:
                    response.close()
                if self.transport is None:
                    transport.close()

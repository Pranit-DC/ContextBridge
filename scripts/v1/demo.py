"""Repeatable online V1 demo, confined to an empty synthetic test store and one call ledger."""

import argparse
import json
import os
import secrets
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from contextbridge.background.runner import WorkRunner
from contextbridge.background.runtime import load_providers
from contextbridge.config import Settings
from contextbridge.db import make_engine, make_session_factory
from contextbridge.engine.index_queue import queue_missing_indexes
from contextbridge.inspection.client import HttpViewerClient, ViewerSettings
from contextbridge.inspection.controller import ViewerController
from contextbridge.models import CaptureEvent, CaptureJob, Memory, MemoryEmbedding, WorkItem
from contextbridge.persistence.capture_cleanup import cancel_capture_jobs
from contextbridge.service import MemoryService
from scripts.start_v1 import ROOT, environment
from scripts.v1.budget import Ledger
from scripts.v1.hosts import run_host

PROJECT = "v1-synthetic-demo"


class Demo:
    def __init__(self, settings, directory, port):
        self.settings, self.directory = settings, directory
        self.engine = make_engine(settings)
        self.sessions = make_session_factory(self.engine)
        self.ledger = Ledger(directory / "request-ledger.sqlite")
        self.worker = WorkRunner(self.sessions, settings, load_providers(settings, self.sessions))
        self.url = f"http://127.0.0.1:{port}"
        self.token = settings.api_token.get_secret_value()
        self.viewer = ViewerController(
            HttpViewerClient(ViewerSettings(self.url, self.token, 60), PROJECT),
            session="synthetic-v1-demo",
        )
        self.report = {"started_at": datetime.now(UTC).isoformat(), "checks": [], "hosts": []}

    def record(self, name, passed, **details):
        self.report["checks"].append({"check": name, "passed": bool(passed), **details})
        print(f"{name}: {'passed' if passed else 'not passed'}", flush=True)

    def model_allowed(self):
        return not self.ledger.snapshot()["stopped"]

    def job(self, job_id):
        with self.sessions() as db:
            item = db.scalar(select(WorkItem.id).where(WorkItem.job_id == UUID(job_id)))
        if self.model_allowed():
            self.worker.run(item)
        return item

    def import_statement(self, text, label, *, duplicate=False):
        if not self.model_allowed():
            self.record(label, False, status="unattempted_after_stop")
            return []
        result = self.viewer.import_conversation(
            str(uuid4()),
            datetime.now(UTC).isoformat(),
            json.dumps([{"message_id": "m1", "role": "user", "content": text}]),
        )
        if not result.ok:
            self.record(label, False, status="submission_failed")
            return []
        item = self.job(result.data["job_id"])
        progress = self.viewer.action("processing", result.data["job_id"])
        if not progress.ok:
            self.ledger.stop()
            self.record(label, False, status="status_unavailable")
            return []
        data = progress.data
        self.record(
            label,
            data["status"] == "succeeded"
            and (bool(data["memory_ids"]) or (duplicate and "DUPLICATE" in data["reason_codes"])),
            status=data["status"],
            reasons=data["reason_codes"],
            memory_ids=data["memory_ids"],
        )
        if any(
            code in data["reason_codes"]
            for code in ("PROVIDER_UNAVAILABLE", "INVALID_PROVIDER_OUTPUT", "INVALID_INPUT")
        ):
            self.ledger.stop()
        before = self.ledger.snapshot()
        self.worker.run(item)  # Terminal/pending replay must not make a second model request.
        self.record(label + " replay", self.ledger.snapshot() == before)
        return data["memory_ids"]

    def index(self, label):
        if not self.model_allowed():
            self.record(label, False, status="unattempted_after_stop")
            return
        queued = queue_missing_indexes(self.sessions, self.settings)
        with self.sessions() as db:
            ids = list(
                db.scalars(
                    select(WorkItem.id).where(
                        WorkItem.kind == "reindex", WorkItem.status == "queued"
                    )
                )
            )
        for item in ids:
            if not self.model_allowed():
                break
            self.worker.run(item)
            if self.worker.inspect(item)["status"] != "succeeded":
                self.ledger.stop()
        self.record(label, self.model_allowed(), queued=queued)

    def search(self, text, expected, label, **filters):
        if not self.model_allowed():
            self.record(label, False, status="unattempted_after_stop")
            return
        # Do not first cause an API pacing failure and then silently retry it.
        time.sleep(3.2)
        result = self.viewer.retrieve(text, **filters)
        ids = [row.memory_id for row in result.rows]
        self.record(
            label,
            expected in ids,
            returned_ids=ids,
            notice=result.notice.text if result.notice else None,
        )
        if result.notice and (
            result.notice.level == "error" or "UNAVAILABLE" in result.notice.text
        ):
            self.ledger.stop()

    def flow(self):
        ids = self.import_statement(
            "Use PostgreSQL as primary database for v1-synthetic-demo.", "live AI import"
        )
        if ids:
            database_id = ids[0]
            self.report["observed_import"] = self.viewer.client.inspect(database_id)
            before = self.viewer.open(database_id).detail.expected_version
            with self.sessions() as db:
                count_before = db.scalar(select(func.count()).select_from(Memory))
            again = self.import_statement(
                "Use PostgreSQL as primary database for v1-synthetic-demo.",
                "repeated statement",
                duplicate=True,
            )
            self.report["observed_repeated"] = [
                self.viewer.client.inspect(value) for value in again
            ]
            with self.sessions() as db:
                count_after = db.scalar(select(func.count()).select_from(Memory))
            self.record(
                "repeated statement preserves one memory/version",
                count_after == count_before
                and self.viewer.open(database_id).detail.expected_version == before,
            )
        else:
            saved = self.viewer.save(
                str(uuid4()),
                "Use PostgreSQL as primary database.",
                "Use PostgreSQL as primary database.",
                "DECISION",
            )
            if not saved.ok:
                raise RuntimeError("SYNTHETIC_WRITE_FAILED")
            database_id = saved.data["id"]
            self.record(
                "explicit substitute for incomplete AI import",
                True,
                quality_note="This does not establish successful AI extraction.",
            )
        backup = self.viewer.save(
            str(uuid4()),
            "PostgreSQL backups are retained for fourteen days.",
            "PostgreSQL backups are retained for fourteen days.",
            "FACT",
        )
        daily = self.viewer.save(
            str(uuid4()),
            "PostgreSQL backups run every night.",
            "PostgreSQL backups run every night.",
            "FACT",
        )
        distractor = self.viewer.save(
            str(uuid4()),
            "Use spaces for Python indentation.",
            "Use spaces for Python indentation.",
            "PREFERENCE",
        )
        self.record("explicit saving", backup.ok and daily.ok and distractor.ok)
        self.index("online indexing")
        self.search(
            "Which relational datastore did we select?", database_id, "paraphrased retrieval"
        )
        historic = datetime.now(UTC).isoformat()
        version = self.viewer.open(database_id).detail.expected_version
        changed = self.viewer.correct(
            database_id,
            version,
            "Use SQLite as primary database.",
            "I explicitly correct the database decision: use SQLite instead of PostgreSQL.",
        )
        self.record(
            "evidence-backed correction and history",
            changed.ok and len(self.viewer.open(database_id).detail.history) == version + 1,
        )
        self.index("correction indexing")
        self.search("PostgreSQL", database_id, "historical retrieval", as_of=historic)
        if self.model_allowed():
            result = self.viewer.action(
                "consolidate",
                {
                    "scope": "project",
                    "project_id": PROJECT,
                    "version_ids": [backup.data["version"]["id"], daily.data["version"]["id"]],
                },
            )
            if result.ok and result.data["job_id"]:
                self.job(result.data["job_id"])
                state = self.viewer.action("consolidation_status", result.data["job_id"])
                self.record(
                    "live consolidation",
                    state.ok
                    and state.data["status"] == "succeeded"
                    and bool(state.data["memory_ids"]),
                    result=state.data if state.ok else {},
                )
                if state.ok and state.data["memory_ids"]:
                    self.report["observed_summaries"] = [
                        self.viewer.client.inspect(identifier)
                        for identifier in state.data["memory_ids"]
                    ]
                if state.ok and state.data["status"] in ("failed", "deferred"):
                    self.ledger.stop()
            else:
                self.record("live consolidation", False, status="submission_failed")
        else:
            self.record("live consolidation", False, status="unattempted_after_stop")
        retired = self.viewer.change_lifecycle(backup.data["id"], "retire", 1)
        self.record(
            "retirement and retired listing",
            retired.ok
            and backup.data["id"] in [row.memory_id for row in self.viewer.retired().rows],
        )
        restored = self.viewer.change_lifecycle(
            backup.data["id"],
            "restore",
            1,
            source_version=1,
            evidence="I confirm PostgreSQL backup retention is still fourteen days.",
        )
        self.record(
            "restoration preserves history",
            restored.ok and len(self.viewer.open(backup.data["id"]).detail.history) == 2,
        )
        self.index("restoration indexing")

    def hosts(self):
        request_id = str(uuid4())
        self.report["hosts"].append(
            run_host(
                "codex",
                self.directory,
                self.url,
                self.token,
                f"Call memory_write exactly once with request_id={request_id}, type=FACT, "
                'content="V1 host demonstration uses four synthetic widgets.", '
                'source={kind:"user", interaction:"host-create", '
                'evidence:"V1 host demonstration uses four synthetic widgets."}. '
                "Then inspect its returned ID and report it. Do not call retrieval yet.",
            )
        )
        with self.sessions() as db:
            row = db.scalar(
                select(Memory).where(
                    Memory.developer_id == self.settings.developer_id,
                    Memory.request_id == UUID(request_id),
                )
            )
            identifier = str(row.id) if row else None
        self.record("actual Codex write persisted", identifier is not None)
        if identifier is None:
            return
        self.index("actual host memory indexing")
        search = "memory_retrieve" if self.model_allowed() else "memory_search"
        self.report["hosts"].append(
            run_host(
                "claude",
                self.directory,
                self.url,
                self.token,
                f"In this fresh session, call {search} exactly once "
                'with query="synthetic widgets". '
                f"Inspect memory_id={identifier}. Then explicitly correct it using memory_update, "
                f'memory_id="{identifier}", expected_version=1, '
                'content="V1 host demonstration uses five synthetic widgets.", '
                'source={kind:"user", interaction:"host-correction", '
                'evidence:"I correct four widgets to five synthetic widgets."}. '
                "Inspect and report the preserved history. These synthetic writes are authorized.",
            )
        )
        detail = self.viewer.open(identifier).detail
        self.record(
            "actual Claude correction preserved history",
            detail is not None and detail.expected_version == 2,
        )
        if detail is None or detail.expected_version != 2:
            return
        self.report["hosts"].append(
            run_host(
                "codex",
                self.directory,
                self.url,
                self.token,
                f"Inspect memory_id={identifier}. "
                "Call memory_retire with that ID and expected_version=2. "
                f"Then call memory_restore with memory_id={identifier}, "
                "expected_version=2, source_version=2, "
                'source={kind:"user",interaction:"host-restore",'
                'evidence:"I confirm five synthetic widgets apply again."}. '
                "Inspect and report three versions. "
                "Retirement and restoration are explicitly authorized.",
            )
        )
        detail = self.viewer.open(identifier).detail
        self.record(
            "actual Codex retirement/restoration",
            detail is not None and detail.expected_version == 3,
        )
        self.report["hosts"].append(
            run_host(
                "claude",
                self.directory,
                self.url,
                self.token,
                f"Inspect memory_id={identifier} and report its evidence/history. "
                "I explicitly authorize permanent forgetting of this synthetic memory: "
                f"call memory_forget with memory_id={identifier}. "
                "Verify by memory_search for synthetic widgets; do not recreate it.",
            )
        )
        self.record(
            "actual Claude permanent forgetting", self.viewer.open(identifier).detail is None
        )

    def cleanup(self):
        with self.sessions() as db:
            ids = list(
                db.scalars(
                    select(Memory.id).where(Memory.developer_id == self.settings.developer_id)
                )
            )
            for identifier in ids:
                if db.get(Memory, identifier) is not None:
                    MemoryService(db, self.settings.developer_id).forget(identifier)
            jobs = list(
                db.scalars(
                    select(CaptureJob.id)
                    .join(CaptureEvent)
                    .where(
                        CaptureEvent.developer_id == self.settings.developer_id,
                        CaptureEvent.project_id == PROJECT,
                    )
                )
            )
            cancel_capture_jobs(db, jobs)
            db.commit()
            self.record(
                "synthetic content cleanup",
                db.scalar(select(func.count()).select_from(Memory)) == 0
                and db.scalar(select(func.count()).select_from(MemoryEmbedding)) == 0
                and db.scalar(
                    select(func.count())
                    .select_from(CaptureEvent)
                    .where(CaptureEvent.payload.is_not(None))
                )
                == 0,
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18766)
    parser.add_argument("--hosts", action="store_true")
    parser.add_argument("--free-groq-confirmed", action="store_true")
    args = parser.parse_args()
    database = os.environ.get("CONTEXTBRIDGE_V1_DEMO_DATABASE_URL", "")
    try:
        url = make_url(database)
        if url.host != "127.0.0.1" or url.database != "contextbridge_v1_live_test":
            raise ValueError("ISOLATED_DEMO_REQUIRED")
        args.directory = args.directory.resolve()
        args.directory.mkdir(parents=True, exist_ok=True)
        if (args.directory / "report.json").exists():
            raise ValueError("DEMO_ALREADY_RECORDED")
        env = environment(args.env_file, project=PROJECT, free_confirmed=args.free_groq_confirmed)
        env.update(
            CONTEXTBRIDGE_DATABASE_URL=database,
            CONTEXTBRIDGE_API_TOKEN=secrets.token_hex(24),
            CONTEXTBRIDGE_DEVELOPER_ID=f"v1-demo-{uuid4().hex[:12]}",
            CONTEXTBRIDGE_WORKER_FACTORY="",
            CONTEXTBRIDGE_CAPTURE_ALLOW_DEVELOPER="false",
            CONTEXTBRIDGE_INTEGRATION_FACTORY="scripts.v1.factory:make",
            CONTEXTBRIDGE_CONSOLIDATION_ENABLED="false",
            CONTEXTBRIDGE_WORKER_MAX_ATTEMPTS="1",
            CONTEXTBRIDGE_V1_DEMO_LEDGER=str(args.directory / "request-ledger.sqlite"),
        )
        os.environ.update(env)
        settings = Settings(_env_file=None)
        engine = make_engine(settings)
        with make_session_factory(engine)() as db:
            if any(
                db.scalar(select(func.count()).select_from(model))
                for model in (Memory, CaptureEvent, WorkItem)
            ):
                raise ValueError("EMPTY_SYNTHETIC_STORE_REQUIRED")
        engine.dispose()
        demo = Demo(settings, args.directory, args.port)
    except Exception:
        print(
            "Demo preflight failed. Use a new migrated contextbridge_v1_live_test database, "
            "private hosted configuration, Free-plan confirmation and unused report directory."
        )
        return 1
    process = None
    try:
        with (args.directory / "api.log").open("w") as log:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "contextbridge.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(args.port),
                ],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=log,
            )
            for _ in range(60):
                if process.poll() is not None:
                    raise RuntimeError("DEMO_API_UNAVAILABLE")
                if demo.viewer.status().ready:
                    break
                time.sleep(0.5)
            else:
                raise RuntimeError("DEMO_API_UNAVAILABLE")
            demo.flow()
            if args.hosts:
                demo.hosts()
    except Exception:
        demo.report["execution_error"] = "DEMO_CHECK_UNAVAILABLE"
        print("A demo check was unavailable. Provider calls will not be retried.", flush=True)
        demo.ledger.stop()
    finally:
        try:
            demo.cleanup()
        except Exception:
            demo.report["cleanup_error"] = "CLEANUP_PENDING"
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        demo.report["budget"] = demo.ledger.snapshot()
        with demo.ledger.db() as db:
            demo.report["requests"] = [
                dict(zip(("id", "provider", "status", "latency_ms"), row, strict=True))
                for row in db.execute("SELECT * FROM requests ORDER BY id")
            ]
        demo.report["finished_at"] = datetime.now(UTC).isoformat()
        (args.directory / "report.json").write_text(
            json.dumps(demo.report, indent=2), encoding="utf-8"
        )
        demo.engine.dispose()
    print(json.dumps(demo.report["budget"]), flush=True)
    return (
        0
        if all(c["passed"] for c in demo.report["checks"])
        and not demo.report.get("execution_error")
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())

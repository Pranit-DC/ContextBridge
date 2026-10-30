"""Real Redis and Linux Celery prefork probes, kept separate from provider quality tests."""

import base64
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        sys.platform == "win32" or not os.getenv("CONTEXTBRIDGE_TEST_BROKER_URL"),
        reason="Real prefork probe requires Linux and a dedicated Redis test broker; "
        "Windows Docker remains pending",
    ),
]

from tests.background.test_work import due, runner, work_id  # noqa: E402
from tests.integration.write_fakes import Harness  # noqa: E402


def until(check, timeout=35):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.2)
    pytest.fail("Worker probe did not reach the expected safe state")


@pytest.fixture
def worker(database, tmp_path):
    celery = pytest.importorskip("celery")
    redis = pytest.importorskip("redis")
    broker_url = os.environ["CONTEXTBRIDGE_TEST_BROKER_URL"]
    # CI/local probes own this separate broker DB. Never flush an ordinary configured broker.
    if not broker_url.endswith("/15") or "127.0.0.1:" not in broker_url:
        pytest.fail("Transport probes require an isolated loopback Redis database 15")
    broker = redis.Redis.from_url(broker_url)
    broker.flushdb()
    app = celery.Celery("probe", broker=broker_url)
    app.conf.update(
        task_publish_retry=False, broker_connection_timeout=2, task_default_queue="contextbridge"
    )
    processes = []
    files = []

    def start(harness, *, crash=False, delay=0, embeddings=False):
        marker = tmp_path / "committed-before-ack"
        env = {
            **os.environ,
            "CONTEXTBRIDGE_DATABASE_URL": database[0],
            "CONTEXTBRIDGE_API_TOKEN": harness.settings.api_token.get_secret_value(),
            "CONTEXTBRIDGE_DEVELOPER_ID": harness.settings.developer_id,
            "CONTEXTBRIDGE_CAPTURE_PROJECT_ID": harness.settings.capture_project_id,
            # Subprocesses read .env; use the harness capture policy, not a user's
            # opt-in grouping/V2 configuration from a real installation.
            **{
                "CONTEXTBRIDGE_" + name.upper(): "" if value is None else str(value)
                for name, value in harness.settings.model_dump().items()
                if name.startswith("capture_")
            },
            "CONTEXTBRIDGE_INTEGRATION_FACTORY": "",
            "CONTEXTBRIDGE_BROKER_URL": broker_url,
            "CONTEXTBRIDGE_WORKER_FACTORY": "tests.background.worker_factory:make",
            "CONTEXTBRIDGE_WORKER_TIMEOUT_SECONDS": "5",
            "CONTEXTBRIDGE_WORKER_MAX_ATTEMPTS": "2",
            "CONTEXTBRIDGE_WORKER_RETRY_SECONDS": "1",
            "CONTEXTBRIDGE_PROBE_DELAY": str(delay),
            "CONTEXTBRIDGE_PROBE_CRASH_MARKER": str(marker) if crash else "",
        }
        command = [
            sys.executable,
            "-m",
            "celery",
            "-A",
            "contextbridge.background.celery_app:app",
            "worker",
            "--loglevel=INFO",
            "--concurrency=1",
            "--hostname=p4-probe@localhost",
        ]
        if embeddings:
            from tests.retrieval.test_cloudflare import BASE_URL, MODEL_ID, SYNTHETIC_KEY

            env.update(
                CONTEXTBRIDGE_WORKER_FACTORY="",
                CONTEXTBRIDGE_INTEGRATION_FACTORY="",
                CONTEXTBRIDGE_EMBEDDING_PROVIDER="cloudflare",
                CONTEXTBRIDGE_EMBEDDING_API_KEY=SYNTHETIC_KEY,
                CONTEXTBRIDGE_EMBEDDING_BASE_URL=BASE_URL,
                CONTEXTBRIDGE_EMBEDDING_MODEL_ID=MODEL_ID,
                CONTEXTBRIDGE_EMBEDDING_DIMENSIONS="",
            )
            # Actual Celery/runtime/HTTP adapter, with synthetic HTTPS only in this subprocess.
            command = [
                sys.executable,
                "-c",
                """
import httpx
from functools import partial
import contextbridge.runtime as runtime
from contextbridge.retrieval.cloudflare import CloudflareEmbeddingBackend
from tests.retrieval.test_cloudflare import response
runtime.CloudflareEmbeddingBackend = partial(
    CloudflareEmbeddingBackend,
    transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response())),
)
from contextbridge.background.celery_app import app
app.worker_main([
    'worker', '--loglevel=INFO', '--concurrency=1', '--hostname=embedding-probe@localhost'
])
""",
            ]
        log = (tmp_path / "worker.log").open("w")
        files.append(log)
        process = subprocess.Popen(
            command,
            cwd=Path(__file__).resolve().parents[2],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        processes.append(process)
        until(lambda: "ready." in (tmp_path / "worker.log").read_text())
        assert process.poll() is None
        return marker

    def publish(item_id):
        app.send_task("contextbridge.execute", args=[item_id], retry=False)

    yield start, publish, broker
    for process in processes:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
    for log in files:
        log.close()
    broker.flushdb()
    broker.close()


def test_real_worker_crash_after_commit_redelivers_once(database, worker):
    from contextbridge.models import MemoryVersion

    harness = Harness(database, worker_timeout_seconds=5)
    job, _, _ = harness.enqueue()
    item = work_id(database, job)
    start, publish, _ = worker
    marker = start(harness, crash=True)
    process = runner(database, harness)
    assert process.dispatch(publish) == 1
    until(marker.exists)
    # The killed prefork child did not acknowledge; Redis/Celery returns the same ID.
    until(lambda: process.inspect(item)["status"] == "succeeded")
    with Session(database[1]) as db:
        assert db.scalar(select(func.count()).select_from(MemoryVersion)) == 1
    publish(str(item))
    time.sleep(0.5)
    assert process.inspect(item)["attempts"] == 1


def test_embedding_only_real_worker_starts_without_factory_and_indexes(database, worker):
    from contextbridge.background.runner import WorkRunner
    from contextbridge.db import make_session_factory
    from contextbridge.engine.index_queue import queue_missing_indexes
    from contextbridge.models import MemoryEmbedding, WorkItem
    from tests.integration.retrieval_fakes import create
    from tests.retrieval.test_cloudflare import MODEL_ID

    harness = Harness(database)
    capture, _, _ = harness.enqueue()
    create(database)
    settings = harness.settings.model_copy(
        update={
            "embedding_provider": "cloudflare",
            "embedding_model_id": MODEL_ID,
            "embedding_dimensions": 1024,
        }
    )
    sessions = make_session_factory(database[1])
    assert queue_missing_indexes(sessions, settings) == 1
    with sessions() as db:
        item = db.scalar(select(MemoryEmbedding))
        assert item is None
        item = db.scalar(select(WorkItem.id).where(WorkItem.kind == "reindex"))
    start, publish, _ = worker
    start(harness, embeddings=True)
    process = WorkRunner(sessions, settings, None)
    assert process.dispatch(publish) == 1
    until(lambda: process.inspect(item)["status"] == "succeeded")
    publish(str(item))
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(MemoryEmbedding)) == 1
        assert db.scalar(select(MemoryEmbedding.dimensions)) == 1024
    assert process.inspect(work_id(database, capture))["attempts"] == 0


def test_real_worker_timeout_retries_to_safe_failure(database, worker):
    harness = Harness(
        database, worker_timeout_seconds=5, worker_max_attempts=2, worker_retry_seconds=1
    )
    job, _, _ = harness.enqueue()
    item = work_id(database, job)
    start, publish, _ = worker
    start(harness, delay=30)
    process = runner(database, harness)
    process.dispatch(publish)
    until(lambda: process.inspect(item)["status"] == "queued")
    # queued is also its initial state; wait for the first finished execution explicitly.
    until(
        lambda: (
            process.inspect(item)["attempts"] == 1
            and process.inspect(item)["reason_code"] == "PROVIDER_UNAVAILABLE"
        )
    )
    due(database, item)
    process.dispatch(publish)
    until(lambda: process.inspect(item)["status"] == "failed")
    assert process.inspect(item)["attempts"] == 2


def test_actual_broker_outage_then_recovery_keeps_id_only_message(database, worker):
    celery = pytest.importorskip("celery")
    harness = Harness(database)
    job, _, _ = harness.enqueue("Synthetic private memory for an ID-only broker probe.")
    item = work_id(database, job)
    _, publish, broker = worker
    unavailable = celery.Celery("unavailable", broker="redis://127.0.0.1:1/15")
    unavailable.conf.update(
        broker_connection_timeout=1,
        task_publish_retry=False,
        broker_transport_options={"socket_connect_timeout": 1, "socket_timeout": 1},
    )
    process = runner(database, harness)
    assert (
        process.dispatch(
            lambda value: unavailable.send_task("contextbridge.execute", args=[value], retry=False)
        )
        == 0
    )
    assert process.inspect(item)["attempts"] == 0
    due(database, item)
    assert process.dispatch(publish) == 1
    encoded = broker.lrange("contextbridge", 0, -1)
    assert len(encoded) == 1
    envelope = json.loads(encoded[0])
    args, kwargs, _ = json.loads(base64.b64decode(envelope["body"]))
    assert args == [str(item)] and kwargs == {}

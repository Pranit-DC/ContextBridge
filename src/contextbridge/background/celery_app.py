"""Linux-container transport. Import requires the optional workers extra."""

import logging
import time
from datetime import UTC, datetime, timedelta
from uuid import UUID

from celery import Celery
from celery.signals import worker_init

from contextbridge.background.maintenance import dispatch_cycle
from contextbridge.background.runner import WorkRunner
from contextbridge.background.runtime import load_providers
from contextbridge.config import Settings
from contextbridge.db import make_engine, make_session_factory
from contextbridge.engine.errors import ModuleError

settings = Settings()
app = Celery("contextbridge", broker=settings.broker_url.get_secret_value())
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    task_ignore_result=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=settings.worker_timeout_seconds + 1,
    task_time_limit=settings.worker_timeout_seconds + 5,
    broker_connection_retry_on_startup=True,
    broker_connection_max_retries=5,
    broker_transport_options={
        "visibility_timeout": settings.worker_timeout_seconds + 30,
        "socket_connect_timeout": 2,
        "socket_timeout": 2,
    },
    broker_connection_timeout=2,
    task_publish_retry=False,
    worker_hijack_root_logger=False,
    worker_enable_remote_control=True,
    task_send_sent_event=False,
    worker_send_task_events=False,
    task_default_queue="contextbridge",
    enable_utc=True,
)


@worker_init.connect
def require_factory(**kwargs):
    if settings.worker_factory is None and settings.integration_factory is None:
        raise SystemExit("Worker unavailable: PROVIDER_UNAVAILABLE (configure a provider factory)")


@app.task(name="contextbridge.execute")
def execute(item_id):
    deadline = datetime.now(UTC) + timedelta(seconds=settings.worker_timeout_seconds)
    engine = make_engine(settings)
    try:
        sessions = make_session_factory(engine)
        runner = WorkRunner(sessions, settings, None)
        try:
            runner.providers = load_providers(settings, sessions)
        except Exception:
            claimed = runner.claim(UUID(str(item_id)))
            if claimed is not None:
                runner.finish(
                    UUID(str(item_id)),
                    claimed[0],
                    0,
                    ModuleError("PROVIDER_UNAVAILABLE", retryable=True),
                )
            return
        runner.run(item_id, deadline=deadline)
    except Exception:
        # DB recovery republishes an unfinished ID. Never log arbitrary provider/DB text.
        logging.getLogger(__name__).error("work_unavailable reason=STORAGE_UNAVAILABLE")
    finally:
        engine.dispose()


def publish(item_id):
    app.send_task("contextbridge.execute", args=[item_id], retry=False)


def main():
    logging.basicConfig(level=logging.INFO)
    engine = make_engine(settings)
    runner = WorkRunner(make_session_factory(engine), settings, None)
    try:
        while True:
            try:
                dispatch_cycle(runner, publish)
            except Exception:
                logging.getLogger(__name__).error(
                    "scheduler_unavailable reason=STORAGE_UNAVAILABLE"
                )
            time.sleep(2)
    except KeyboardInterrupt:
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())

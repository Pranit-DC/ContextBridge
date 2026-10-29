"""DB leases and domain commits establish replay safety; broker acknowledgments do not."""

import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError

from contextbridge.background.outbox import FenceLost, check_fence, enqueue_work
from contextbridge.engine.consolidation import ConsolidationService
from contextbridge.engine.errors import EngineError, ModuleError
from contextbridge.engine.indexing import IndexService
from contextbridge.engine.write import UNRESOLVED_REASONS, WriteEngine
from contextbridge.models import CaptureEvent, CaptureJob, ConsolidationJob, ReindexJob, WorkItem
from contextbridge.persistence.locks import lock_owner

logger = logging.getLogger(__name__)
TERMINAL = {"succeeded", "failed", "cancelled"}


def is_finished(job):
    return job.status in TERMINAL or (job.status == "deferred" and not job.retryable)


@dataclass(frozen=True)
class DomainState:
    status: str
    retryable: bool = False
    reason_codes: tuple[str, ...] = ()


class WorkRunner:
    def __init__(self, sessions, settings, providers, *, readiness_policy=None):
        self.sessions, self.settings, self.providers = sessions, settings, providers
        self.readiness_policy = readiness_policy

    def binding(self, model):
        project = (model.scope == "project") & (
            model.project_id == self.settings.capture_project_id
        )
        return (
            or_(project, model.scope == "developer")
            if self.settings.capture_allow_developer
            else project
        )

    def item(self, session, item_id):
        item = session.scalar(
            select(WorkItem)
            .where(
                WorkItem.id == item_id,
                WorkItem.developer_id == self.settings.developer_id,
                self.binding(WorkItem),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return item

    def domain(self, session, item):
        if item.kind == "capture":
            job = session.scalar(
                select(CaptureJob)
                .join(CaptureEvent, CaptureEvent.id == CaptureJob.event_record_id)
                .where(
                    CaptureJob.id == item.job_id,
                    CaptureEvent.developer_id == self.settings.developer_id,
                    self.binding(CaptureEvent),
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            return job
        model = ReindexJob if item.kind == "reindex" else ConsolidationJob
        return session.scalar(
            select(model)
            .where(
                model.id == item.job_id,
                model.developer_id == self.settings.developer_id,
                self.binding(model),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def group_jobs(self, session, job):
        if job is None:
            return []
        if not isinstance(job, CaptureJob) or job.group_leader_id != job.id:
            return [job]
        jobs = session.scalars(
            select(CaptureJob)
            .join(CaptureEvent)
            .where(
                CaptureJob.group_leader_id == job.id,
                CaptureEvent.developer_id == self.settings.developer_id,
                self.binding(CaptureEvent),
            )
            .order_by(CaptureJob.id)
            .limit(21)
            .execution_options(populate_existing=True)
        ).all()
        if len(jobs) > 20:
            raise ModuleError("INVALID_PROVIDER_OUTPUT")
        return jobs

    def domain_state(self, session, job):
        """Aggregate group execution without rewriting any source job's saved outcome."""
        jobs = self.group_jobs(session, job)
        if not jobs or any(member.status == "cancelled" for member in jobs):
            return DomainState("cancelled", reason_codes=("CANCELLED",))
        unfinished = [member for member in jobs if not is_finished(member)]
        if unfinished:
            # A terminal/deferred leader cannot abandon a pending or retryable follower.
            reasons = tuple(
                sorted(
                    {
                        reason
                        for member in unfinished
                        for reason in member.reason_codes
                        if reason not in UNRESOLVED_REASONS
                    }
                )
            )
            return DomainState("queued", True, reasons)
        failed = [member for member in jobs if member.status == "failed"]
        deferred = [member for member in jobs if member.status == "deferred"]
        reasons = tuple(
            sorted(
                {reason for member in failed or deferred or jobs for reason in member.reason_codes}
            )
        )
        return DomainState(
            "failed" if failed else "deferred" if deferred else "succeeded", reason_codes=reasons
        )

    def claim(self, item_id, *, deadline=None):
        with self.sessions() as session:
            lock_owner(session, self.settings.developer_id)
            item = self.item(session, item_id)
            if (
                item is None
                or item.status in TERMINAL
                or item.status == "deferred"
                or (self.settings.embedding_only and item.kind != "reindex")
            ):
                return None
            now = datetime.now(UTC)
            job = self.domain(session, item)
            state = self.domain_state(session, job)
            if state.status in TERMINAL or (state.status == "deferred" and not state.retryable):
                item.status = state.status
                item.lease_token = item.lease_until = None
                item.updated_at = now
                session.commit()
                return None
            if item.status == "running" and item.lease_until > now:
                return None
            if item.status == "queued" and item.published_at is None and item.available_at > now:
                return None
            if item.kind == "capture":
                from contextbridge.engine.grouping import members
                from contextbridge.engine.ingestion import IngestionService

                ingestion = IngestionService(session, self.settings)
                ingestion._expire(now)
                event = session.get(CaptureEvent, job.event_record_id)
                if event.payload is None:
                    item.status = "cancelled"
                    session.commit()
                    return None
                group = members(ingestion, job, event, policy=self.readiness_policy, now=now)
                if group is None:
                    item.published_at = None
                    item.available_at = now + timedelta(seconds=1)
                    session.commit()
                    return None
                if group[0][0].id != job.id:
                    session.commit()
                    return None
            if item.attempts >= self.settings.worker_max_attempts:
                self.failure(session, item, job, "PROVIDER_UNAVAILABLE", False, now)
                session.commit()
                return None
            item.attempts += 1
            item.status, item.lease_token = "running", uuid4()
            item.lease_until = now + timedelta(seconds=self.settings.worker_timeout_seconds)
            if deadline is not None:
                item.lease_until = min(item.lease_until, deadline)
            item.available_at, item.updated_at = item.lease_until, now
            token, kind, job_id = item.lease_token, item.kind, item.job_id
            session.commit()
            return token, kind, job_id

    def inspect(self, item_id):
        with self.sessions() as session:
            lock_owner(session, self.settings.developer_id)
            item = self.item(session, item_id)
            if item is None:
                raise EngineError("OUT_OF_SCOPE", 404)
            job = self.domain(session, item)
            state = self.domain_state(session, job)
            status = state.status if is_finished(state) else item.status
            result = {
                "work_id": str(item.id),
                "job_id": str(item.job_id),
                "kind": item.kind,
                "status": status,
                "attempts": item.attempts,
                "reason_code": item.reason_code,
                "duration_ms": item.duration_ms,
                "updated_at": item.updated_at,
            }
            session.commit()
            return result

    def failure(self, session, item, job, code, retryable, now):
        retry = retryable and item.attempts < self.settings.worker_max_attempts
        item.status, item.reason_code = ("queued" if retry else "failed"), code
        item.available_at = now + timedelta(
            seconds=min(300, self.settings.worker_retry_seconds * 2 ** (item.attempts - 1))
        )
        item.lease_token = item.lease_until = item.published_at = None
        item.updated_at = now
        for member in self.group_jobs(session, job):
            if is_finished(member):
                continue
            member.status, member.retryable, member.reason_codes, member.updated_at = (
                "deferred" if retry else "failed",
                retry,
                sorted((set(member.reason_codes) & UNRESOLVED_REASONS) | {code}),
                now,
            )
            if isinstance(member, ConsolidationJob) and not retry:
                member.proposals = None

    def finish(self, item_id, token, duration, error=None):
        with self.sessions() as session:
            lock_owner(session, self.settings.developer_id)
            check_fence(session, item_id, token, allow_expired=True)
            item = self.item(session, item_id)
            job = self.domain(session, item)
            state = self.domain_state(session, job)
            now = datetime.now(UTC)
            if state.status in TERMINAL or (state.status == "deferred" and not state.retryable):
                item.status = state.status
                item.reason_code = (state.reason_codes or (None,))[0]
                item.lease_token = item.lease_until = None
                item.updated_at = now
            else:
                code = error.code if error else (state.reason_codes or ("PROVIDER_UNAVAILABLE",))[0]
                retryable = error.retryable if error else state.retryable
                self.failure(session, item, job, code, retryable, now)
            item.duration_ms = duration
            status, code = item.status, item.reason_code
            session.commit()
        logger.info(
            "work_finished work_id=%s status=%s reason=%s duration_ms=%s",
            item_id,
            status,
            code,
            duration,
        )

    def run(self, item_id, *, deadline=None):
        try:
            item_id = UUID(str(item_id))
        except (ValueError, TypeError):
            return
        claimed = self.claim(item_id, deadline=deadline)
        if claimed is None:
            return
        token, kind, job_id = claimed
        started = time.monotonic()
        error = None
        try:
            providers = self.providers.fresh()

            def before_call():
                with self.sessions() as db:
                    lock_owner(db, self.settings.developer_id)
                    check_fence(db, item_id, token)
                    if kind == "capture":
                        job = self.domain(db, self.item(db, item_id))
                        event = db.get(CaptureEvent, job.event_record_id)
                        if event.payload is None or event.expires_at <= datetime.now(UTC):
                            raise ModuleError("CANCELLED")
                        if job.group_leader_id is not None:
                            from contextbridge.engine.grouping import members
                            from contextbridge.engine.ingestion import IngestionService

                            group = members(IngestionService(db, self.settings), job, event)
                            if any(
                                e.payload is None
                                or e.expires_at <= datetime.now(UTC)
                                or j.status == "cancelled"
                                for j, e in group
                            ):
                                raise ModuleError("CANCELLED")
                    elif kind == "consolidation":
                        service = ConsolidationService(db, self.settings)
                        job = service.locked_job(job_id)
                        if job.status == "cancelled":
                            raise ModuleError("CANCELLED")
                        service.sources(job)
                    db.commit()

            providers.bind_guard(before_call)
            with self.sessions() as session:

                def guard(db):
                    check_fence(db, item_id, token)

                if kind == "capture":
                    WriteEngine(
                        session, self.settings, providers.modules, commit_guard=guard
                    ).process(job_id)
                elif kind == "reindex":
                    IndexService(session, self.settings.developer_id, commit_guard=guard).process(
                        job_id, providers.embedder
                    )
                else:
                    ConsolidationService(session, self.settings, commit_guard=guard).process(
                        job_id, providers.modules.consolidator
                    )
        except FenceLost:
            # An expired current token may record a bounded retry. Cancellation or a newer
            # token still prevents finish from touching any domain state.
            error = ModuleError("PROVIDER_UNAVAILABLE", retryable=True)
        except SQLAlchemyError:
            error = ModuleError("STORAGE_UNAVAILABLE", retryable=True)
        except ModuleError as exc:
            error = ModuleError(exc.code, retryable=exc.retryable)
        except Exception:
            error = ModuleError("INVALID_PROVIDER_OUTPUT")
        try:
            self.finish(item_id, token, int((time.monotonic() - started) * 1000), error)
        except FenceLost:
            pass

    def backfill(self):
        """Bounded recovery of accepted jobs that predate the P4 schema/outbox."""
        with self.sessions() as session:
            lock_owner(session, self.settings.developer_id)
            for kind, model in [
                ("capture", CaptureJob),
                ("reindex", ReindexJob),
                ("consolidation", ConsolidationJob),
            ]:
                if self.settings.embedding_only and kind != "reindex":
                    continue
                if kind == "capture":
                    stmt = (
                        select(model, CaptureEvent)
                        .join(CaptureEvent, CaptureEvent.id == CaptureJob.event_record_id)
                        .where(
                            CaptureEvent.developer_id == self.settings.developer_id,
                            self.binding(CaptureEvent),
                        )
                    )
                else:
                    stmt = select(model).where(
                        model.developer_id == self.settings.developer_id, self.binding(model)
                    )
                stmt = (
                    stmt.where(
                        or_(
                            model.status.in_(["queued", "running"]),
                            (model.status == "deferred") & model.retryable,
                        ),
                        ~select(WorkItem.id)
                        .where(WorkItem.kind == kind, WorkItem.job_id == model.id)
                        .exists(),
                    )
                    .order_by(model.id)
                    .limit(100)
                )
                for row in session.execute(stmt):
                    job, scope_row = (row[0], row[1]) if kind == "capture" else (row[0], row[0])
                    if job.status != "deferred" or job.retryable:
                        enqueue_work(
                            session,
                            kind,
                            job.id,
                            self.settings.developer_id,
                            scope_row.scope,
                            scope_row.project_id,
                        )
            session.commit()

    def dispatch(self, publish, *, limit=100):
        count = 0
        # Publishing while holding a bounded row lock makes the DB mark follow the send.
        # A crash between them republishes the ID; the domain/lease check handles duplication.
        with self.sessions() as session:
            now = datetime.now(UTC)
            items = session.scalars(
                select(WorkItem)
                .where(
                    WorkItem.developer_id == self.settings.developer_id,
                    self.binding(WorkItem),
                    WorkItem.kind == "reindex" if self.settings.embedding_only else True,
                    WorkItem.status.in_(["queued", "running"]),
                    WorkItem.available_at <= now,
                )
                .order_by(WorkItem.available_at, WorkItem.id)
                .limit(min(max(limit, 1), 100))
                .with_for_update(skip_locked=True)
            ).all()
            for item in items:
                try:
                    publish(str(item.id))
                except Exception:
                    # Broker outages never consume a provider execution attempt.
                    item.available_at = now + timedelta(seconds=self.settings.worker_retry_seconds)
                    item.reason_code = "PROVIDER_UNAVAILABLE"
                    continue
                item.published_at = now
                item.available_at = now + timedelta(
                    seconds=self.settings.worker_timeout_seconds + 30
                )
                count += 1
            session.commit()
        return count

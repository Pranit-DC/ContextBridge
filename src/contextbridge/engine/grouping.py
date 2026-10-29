"""Bounded, ID-only grouping over opted-in durable captures, under the owner lock.

Groups freeze before extraction. Receipt order defines arrival order; message order inside
an event is unchanged. Session and agent labels only partition already authorized captures.
"""

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from contextbridge.contracts import CapturedEvent
from contextbridge.engine.errors import ModuleError
from contextbridge.models import CaptureEvent, CaptureJob

SOURCE_INSTANT = re.compile(
    r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?"
    r"(?:Z|[+-]\d{2}:\d{2})(?!\w)"
)


def mentions_effective_instant(candidate):
    """Preserve a proposed instant quoted in the evidence; admission still checks meaning."""
    for literal in SOURCE_INSTANT.findall(candidate.source.evidence):
        try:
            if datetime.fromisoformat(literal) == candidate.valid_from:
                return True
        except ValueError:
            continue
    return False


@dataclass(frozen=True)
class ReadinessPolicy:
    idle_seconds: int = 30
    max_events: int = 5
    max_messages: int = 20
    max_characters: int = 32_000

    def __post_init__(self):
        if not (
            1 <= self.idle_seconds <= 300
            and 1 <= self.max_events <= 20
            and 1 <= self.max_messages <= 20
            and 1 <= self.max_characters <= 32_000
        ):
            raise ValueError("Invalid grouping bounds")

    @classmethod
    def from_settings(cls, settings):
        return cls(
            *(
                getattr(settings, "capture_group_" + name)
                for name in ("idle_seconds", "max_events", "max_messages", "max_characters")
            )
        )

    def ready(self, rows, now, *, overflow=False):
        messages = sum(len(event.payload["messages"]) for _, event in rows)
        size = sum(len(m["content"]) for _, e in rows for m in e.payload["messages"])
        return (
            overflow
            or len(rows) >= self.max_events
            or messages >= self.max_messages
            or size >= self.max_characters
            or now >= rows[-1][1].received_at + timedelta(seconds=self.idle_seconds)
        )


def members(ingestion, job, event, *, policy=None, now=None):
    """Freeze a ready group. None means keep this partial group queued, without an attempt.

    Caller holds the owner lock and commits together with the worker lease. Existing frozen
    groups remain grouped if configuration changes across a restart.
    """
    session, settings = ingestion.session, ingestion.settings
    if job.group_leader_id is not None:
        return session.execute(
            select(CaptureJob, CaptureEvent)
            .join(CaptureEvent)
            .where(
                CaptureJob.group_leader_id == job.group_leader_id,
                CaptureEvent.developer_id == settings.developer_id,
                CaptureEvent.scope == event.scope,
                CaptureEvent.project_id.is_not_distinct_from(event.project_id),
            )
            .order_by(CaptureEvent.received_at, CaptureEvent.id)
        ).all()
    if not settings.capture_grouping_enabled:
        return [(job, event)]
    # Opting in must not strand already interpreted or retryable independent captures.
    if event.extraction_complete or job.status != "queued":
        return [(job, event)]
    if event.payload is None:
        raise ModuleError("CANCELLED")
    policy, now = policy or ReadinessPolicy.from_settings(settings), now or datetime.now(UTC)
    rows = session.execute(
        select(CaptureJob, CaptureEvent)
        .join(CaptureEvent)
        .where(
            CaptureEvent.developer_id == settings.developer_id,
            CaptureEvent.scope == event.scope,
            CaptureEvent.project_id.is_not_distinct_from(event.project_id),
            CaptureEvent.payload["session"].as_string() == event.payload["session"],
            CaptureEvent.payload["agent"].as_string() == event.payload["agent"],
            CaptureEvent.payload.is_not(None),
            CaptureEvent.expires_at > now,
            CaptureEvent.extraction_complete.is_(False),
            CaptureJob.group_leader_id.is_(None),
            CaptureJob.status == "queued",
        )
        .order_by(CaptureEvent.received_at, CaptureEvent.id)
        .limit(policy.max_events + 1)
    ).all()
    batch, count, size = [], 0, 0
    for row in rows:
        messages = row[1].payload["messages"]
        length = sum(len(m["content"]) for m in messages)
        if batch and (
            len(batch) >= policy.max_events
            or count + len(messages) > policy.max_messages
            or size + length > policy.max_characters
        ):
            break
        batch.append(row)
        count, size = count + len(messages), size + length
    if not batch or not policy.ready(batch, now, overflow=len(batch) < len(rows)):
        return None
    # A pre-existing event larger than a configured soft bound runs alone, within V1 limits.
    leader = batch[0][0].id
    for member, _ in batch:
        member.group_leader_id = leader
    return batch


def aggregate(rows):
    """Produce one V1 extractor input plus an ephemeral, reversible provenance map."""
    first = CapturedEvent.model_validate(rows[0][1].payload)
    messages, mapping = [], {}
    for i, (job, event) in enumerate(rows):
        captured = CapturedEvent.model_validate(event.payload)
        for j, message in enumerate(captured.messages):
            alias = f"g{i}m{j}"
            messages.append(message.model_copy(update={"message_id": alias}))
            mapping[alias] = (job.id, captured, message.message_id)
    return first.model_copy(update={"messages": messages}), mapping


def distribute(candidates, mapping, rows):
    """Restore original source IDs. V1 cannot represent a multi-event evidence claim."""
    result = {job.id: [] for job, _ in rows}
    deferred = set()
    aggregate_time = CapturedEvent.model_validate(rows[0][1].payload).occurred_at
    for candidate in candidates:
        refs = [mapping[ref.message_id] for ref in candidate.evidence_refs]
        jobs = {ref[0] for ref in refs}
        if len(jobs) != 1:
            deferred.update(jobs)
            continue
        job_id, event, _ = refs[0]
        source = candidate.source.model_copy(
            update={
                "agent": event.agent,
                "session": event.session,
                "interaction": event.interaction,
            }
        )
        result[job_id].append(
            candidate.model_copy(
                update={
                    "event_id": event.event_id,
                    "source": source,
                    "evidence_refs": [
                        ref.model_copy(
                            update={"event_id": event.event_id, "message_id": original[2]}
                        )
                        for ref, original in zip(candidate.evidence_refs, refs, strict=True)
                    ],
                    "valid_from": event.occurred_at
                    if candidate.valid_from == aggregate_time
                    and not mentions_effective_instant(candidate)
                    else candidate.valid_from,
                }
            )
        )
    return result, deferred

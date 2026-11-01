"""Atomic logical-bundle ingestion over the existing durable capture/outbox store."""

from sqlalchemy import select

from contextbridge.contracts import CapturedEvent
from contextbridge.engine.errors import EngineError
from contextbridge.engine.indexing import identity_fingerprint
from contextbridge.engine.ingestion import IngestionService
from contextbridge.models import CaptureBundle, CaptureEvent, CaptureJob
from contextbridge.security import contains_secret_fields


def ingest_bundle(session, settings, bundle):
    if not settings.capture_evidence_v2_enabled:
        raise EngineError("PROVIDER_UNAVAILABLE", 503)
    if contains_secret_fields(bundle.model_dump(mode="json")):
        raise EngineError("INVALID_INPUT", 422)
    first, messages, mapping = bundle.events[0], [], {}
    for i, event in enumerate(bundle.events):
        for j, message in enumerate(event.messages):
            alias = f"s{i}m{j}"
            messages.append(message.model_copy(update={"message_id": alias}))
            mapping[alias] = {
                "event_id": str(event.event_id),
                "message_id": message.message_id,
                "agent": event.agent,
                "session": event.session,
                "interaction": event.interaction,
                "occurred_at": event.occurred_at.isoformat(),
                "source_timezone": event.source_timezone,
                "role": message.role,
            }
    logical = CapturedEvent(
        schema_version=1,
        event_id=bundle.bundle_id,
        scope=first.scope,
        project_id=first.project_id,
        agent=first.agent,
        session=first.session,
        interaction="bundle-" + identity_fingerprint(bundle.model_dump(mode="json")),
        occurred_at=max(event.occurred_at for event in bundle.events),
        capture_method="manual_import",
        messages=messages,
    )
    service = IngestionService(session, settings)
    result = service.ingest(logical, commit=False)
    event = session.scalar(
        select(CaptureEvent).where(
            CaptureEvent.developer_id == settings.developer_id,
            CaptureEvent.event_id == bundle.bundle_id,
        )
    )
    metadata = {"schema_version": 2, "bundle_id": str(bundle.bundle_id), "messages": mapping}
    existing = session.get(CaptureBundle, event.id)
    if existing is None:
        if result.status == "duplicate":
            raise EngineError("VERSION_CONFLICT", 409)
        session.add(CaptureBundle(event_record_id=event.id, metadata_json=metadata))
    elif existing.metadata_json != metadata:
        raise EngineError("VERSION_CONFLICT", 409)
    job = session.get(CaptureJob, result.job_id)
    job.group_leader_id = job.id  # Frozen logical group; never mix it with a V1 group.
    session.commit()
    return result

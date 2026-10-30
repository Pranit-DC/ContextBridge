"""Validate ephemeral pointers and persist visible provenance in the shared transaction."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select

from contextbridge.engine.errors import ModuleError
from contextbridge.engine.indexing import identity_fingerprint
from contextbridge.evidence_time.contracts import CandidateMetadata
from contextbridge.evidence_time.temporal import TemporalAmbiguity, bounds
from contextbridge.models import (
    CandidateProvenance,
    CaptureBundle,
    CaptureCandidate,
    CaptureEvent,
    CaptureJob,
    VersionProvenance,
)
from contextbridge.security import contains_secret_fields


def bundle_metadata(session, developer_id, event):
    row = session.scalar(
        select(CaptureEvent).where(
            CaptureEvent.developer_id == developer_id,
            CaptureEvent.event_id == UUID(str(event["event_id"])),
        )
    )
    if row is None or row.payload is None or row.expires_at <= datetime.now(UTC):
        raise ModuleError("CANCELLED")
    if row.payload != event:
        raise ModuleError("VERSION_CONFLICT")
    bundle = session.get(CaptureBundle, row.id)
    return bundle.metadata_json if bundle else None


def fragments(event, mapping, pointers):
    messages = {m["message_id"]: m for m in event["messages"]}
    result = []
    try:
        for pointer in pointers:
            alias = pointer.message_id
            message, trace = messages[alias], mapping[alias]
            if (
                message["role"] not in {"user", "tool"}
                or trace["role"] != message["role"]
                or pointer.end > len(message["content"])
            ):
                raise ModuleError("INVALID_PROVIDER_OUTPUT")
            result.append(
                {
                    **trace,
                    "quote": message["content"][pointer.start : pointer.end],
                    "message_alias": alias,
                }
            )
    except (KeyError, TypeError, IndexError):
        raise ModuleError("INVALID_PROVIDER_OUTPUT") from None
    if len({f["message_alias"] for f in result}) != len(result) or contains_secret_fields(result):
        raise ModuleError("INVALID_PROVIDER_OUTPUT")
    return result


def validate_extension(event, metadata, candidate, raw):
    parsed = CandidateMetadata.model_validate(raw)
    if parsed.candidate_fingerprint != identity_fingerprint(candidate.model_dump(mode="json")):
        raise ModuleError("INVALID_PROVIDER_OUTPUT")
    source = fragments(event, metadata["messages"], parsed.fragments)
    if {r.message_id for r in candidate.evidence_refs} != {f["message_alias"] for f in source}:
        raise ModuleError("INVALID_PROVIDER_OUTPUT")
    derived = bounds(
        [{"message_id": f["message_alias"], "quote": f["quote"]} for f in source],
        metadata["messages"],
        parsed.temporal.relation,
    )
    if derived != parsed.temporal or candidate.valid_from != derived.guaranteed_from:
        raise ModuleError("INVALID_PROVIDER_OUTPUT")
    render(
        source, parsed.temporal.model_dump(mode="json")
    )  # Check full evidence bound before admission.
    return parsed


def render(source, temporal):
    text = "Verified source bundle (each quote remains attributed):\n"
    text += "\n".join(
        f"[{f['role']}; event={f['event_id']}; message={f['message_id']}; "
        f"agent={f['agent']}; session={f['session']}; interaction={f['interaction']}; "
        f"occurred_at={f['occurred_at']}; timezone={f['source_timezone']}]\n{f['quote']}"
        for f in source
    )
    text += "\nTemporal metadata: " + str(temporal)
    if len(text) > 8000 or contains_secret_fields(text):
        raise ModuleError("INVALID_PROVIDER_OUTPUT")
    return text


def save_candidate(session, settings, event, captured, row, candidate, extractor):
    metadata = session.get(CaptureBundle, event.id)
    if metadata is None:
        return False
    if not settings.capture_evidence_v2_enabled:
        raise ModuleError("PROVIDER_UNAVAILABLE")
    raw = getattr(extractor, "extensions", {}).get(str(candidate.candidate_id))
    if raw is None:
        raise ModuleError("INVALID_PROVIDER_OUTPUT")
    extension = validate_extension(
        captured.model_dump(mode="json"), metadata.metadata_json, candidate, raw
    )
    session.flush()
    session.add(
        CandidateProvenance(
            candidate_record_id=row.id, metadata_json=extension.model_dump(mode="json")
        )
    )
    return True


def applied(session, settings, row, candidate, version, previous=None):
    extension = session.get(CandidateProvenance, row.id)
    if extension is None:
        return
    parsed = CandidateMetadata.model_validate(extension.metadata_json)
    job = session.get(CaptureJob, row.job_id)
    event = session.get(CaptureEvent, job.event_record_id)
    if event.payload is None or event.expires_at <= datetime.now(UTC):
        raise ModuleError("CANCELLED")
    metadata = session.get(CaptureBundle, event.id)
    if metadata is None:
        raise ModuleError("CANCELLED")
    validate_extension(event.payload, metadata.metadata_json, candidate, extension.metadata_json)
    source = fragments(event.payload, metadata.metadata_json["messages"], parsed.fragments)
    temporal = parsed.temporal.model_dump(mode="json")
    value = {
        "schema_version": 2,
        "bundle_id": str(event.event_id),
        "fragments": source,
        "temporal": temporal,
    }
    if contains_secret_fields(value):
        raise ModuleError("INVALID_PROVIDER_OUTPUT")
    session.add(
        VersionProvenance(
            version_id=version.id,
            previous_version_id=previous.id if previous else None,
            metadata_json=value,
        )
    )
    # Accurate tool-produced composite, not a pretend quotation from one human turn.
    version.evidence = render(source, temporal)
    version.source_kind = "tool"
    version.source_agent = "ContextBridge-evidence-bundle"


def transition_start(session, row, candidate, previous):
    extension = session.get(CandidateProvenance, row.id)
    if extension is None:
        return candidate.valid_from
    temporal = CandidateMetadata.model_validate(extension.metadata_json).temporal
    start = temporal.earliest if temporal.relation == "state_transition" else candidate.valid_from
    if previous is not None and start < previous.valid_from:
        raise TemporalAmbiguity()
    return start


def purge_ephemeral(session, *, event_ids=None, job_ids=None, candidate_ids=None):
    if event_ids is not None:
        session.execute(delete(CaptureBundle).where(CaptureBundle.event_record_id.in_(event_ids)))
    if job_ids is not None:
        candidate_ids = select(CaptureCandidate.id).where(CaptureCandidate.job_id.in_(job_ids))
    if candidate_ids is not None:
        session.execute(
            delete(CandidateProvenance).where(
                CandidateProvenance.candidate_record_id.in_(candidate_ids)
            )
        )

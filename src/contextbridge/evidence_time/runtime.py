"""Task-local adapters reuse current providers and the one capture engine/store."""

from uuid import UUID

from sqlalchemy import select

from contextbridge.contracts import Candidate, CapturedEvent
from contextbridge.engine.errors import ModuleError
from contextbridge.engine.indexing import identity_fingerprint
from contextbridge.engine.modules import validate_evidence
from contextbridge.evidence_time.provider import AUDIT, BatchAudit, BundleProvider
from contextbridge.evidence_time.storage import bundle_metadata, validate_extension
from contextbridge.formation.providers.chat import parse_object
from contextbridge.models import CandidateProvenance, CaptureCandidate, CaptureEvent, CaptureJob


class BundleAwareExtractor:
    def __init__(self, legacy, client, sessions, settings):
        self.legacy, self.client, self.sessions, self.settings = legacy, client, sessions, settings
        self.provider = BundleProvider(client) if client else None
        self.active_bundle = False

    @property
    def extensions(self):
        return self.provider.extensions if self.provider else {}

    @property
    def needs_confirmation(self):
        return (
            self.provider.needs_confirmation
            if self.active_bundle
            else getattr(self.legacy, "needs_confirmation", False)
        )

    def extract(self, event):
        with self.sessions() as session:
            metadata = bundle_metadata(session, self.settings.developer_id, event)
        self.active_bundle = metadata is not None
        if metadata is None:
            return self.legacy.extract(event)
        if self.provider is None:
            raise ModuleError("PROVIDER_UNAVAILABLE")
        return self.provider.extract(event, metadata)


class BundleAwareVerifier:
    """One bounded independent audit per frozen bundle, with hash/verdict-only task cache."""

    def __init__(self, legacy, client, sessions, settings):
        self.legacy, self.client, self.sessions, self.settings = legacy, client, sessions, settings
        self.event_key = None
        self.verdicts = {}

    def verify(self, candidate, event):
        with self.sessions() as session:
            metadata = bundle_metadata(session, self.settings.developer_id, event)
            if metadata is not None:
                current_key = identity_fingerprint([event, metadata])
                if current_key != self.event_key:
                    self.event_key, self.verdicts = current_key, {}
                rows = session.execute(
                    select(CaptureCandidate, CandidateProvenance)
                    .join(
                        CandidateProvenance,
                        CandidateProvenance.candidate_record_id == CaptureCandidate.id,
                    )
                    .join(CaptureJob, CaptureJob.id == CaptureCandidate.job_id)
                    .join(CaptureEvent, CaptureEvent.id == CaptureJob.event_record_id)
                    .where(
                        CaptureEvent.developer_id == self.settings.developer_id,
                        CaptureEvent.event_id == UUID(event["event_id"]),
                        CaptureCandidate.developer_id == self.settings.developer_id,
                        CaptureCandidate.payload.is_not(None),
                    )
                    .order_by(CaptureCandidate.position)
                    .limit(21)
                ).all()
                if not rows or len(rows) > 20:
                    raise ModuleError("INVALID_PROVIDER_OUTPUT")
                proposed = []
                requested_key = None
                captured = CapturedEvent.model_validate(event)
                for row, extension in rows:
                    parsed = Candidate.model_validate(row.payload)
                    validate_evidence(captured, parsed)
                    provenance = validate_extension(
                        event, metadata, parsed, extension.metadata_json
                    )
                    key = identity_fingerprint([row.payload, extension.metadata_json])
                    if str(parsed.candidate_id) == candidate["candidate_id"]:
                        if row.payload != candidate or row.status != "pending":
                            raise ModuleError("INVALID_PROVIDER_OUTPUT")
                        requested_key = key
                    if row.status == "pending":
                        proposed.append((key, parsed, provenance))
                if requested_key is None:
                    raise ModuleError("INVALID_PROVIDER_OUTPUT")
                if requested_key in self.verdicts:
                    return self.verdicts[requested_key]
        # No database transaction or authorization lock during hosted/quota waits.
        if metadata is None:
            return self.legacy.verify(candidate, event)
        if self.client is None:
            raise ModuleError("PROVIDER_UNAVAILABLE")
        raw = self.client.complete(
            self.client.settings.model,
            AUDIT,
            {
                "original_event": event,
                "sources": metadata["messages"],
                "candidates": [
                    {
                        "candidate_id": str(parsed.candidate_id),
                        "candidate": parsed.model_dump(
                            mode="json",
                            include={"content", "type", "conditions", "scope", "project_id"},
                        ),
                        "fragments": [f.model_dump() for f in provenance.fragments],
                        "temporal": provenance.temporal.model_dump(
                            mode="json", exclude={"normalized_evidence"}
                        ),
                    }
                    for _, parsed, provenance in proposed
                ],
            },
            BatchAudit,
        )
        result = BatchAudit.model_validate(parse_object(raw))
        checks = {str(item.candidate_id): item for item in result.checks}
        if len(checks) != len(result.checks) or set(checks) != {
            str(parsed.candidate_id) for _, parsed, _ in proposed
        }:
            raise ModuleError("INVALID_PROVIDER_OUTPUT")
        verdicts = {}
        for key, parsed, provenance in proposed:
            check = checks[str(parsed.candidate_id)]
            conditions = {p.key: p.value for p in check.conditions}
            if len(conditions) != len(check.conditions):
                raise ModuleError("INVALID_PROVIDER_OUTPUT")
            if check.scope != "bound":
                support = "unsupported" if check.scope == "other" else "uncertain"
            elif (
                check.kind != parsed.type
                or conditions != parsed.conditions
                or check.temporal_relation != provenance.temporal.relation
            ):
                support = "uncertain"
            else:
                support = check.support
            verdicts[key] = support
        self.verdicts = (
            verdicts  # No source text, provider response or shared/session-global cache.
        )
        return self.verdicts[requested_key]

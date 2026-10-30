"""Task-local adapters reuse current providers and the one capture engine/store."""

from uuid import UUID

from sqlalchemy import select

from contextbridge.contracts import Candidate
from contextbridge.engine.errors import ModuleError
from contextbridge.evidence_time.contracts import CandidateMetadata
from contextbridge.evidence_time.provider import AUDIT, Audit, BundleProvider
from contextbridge.evidence_time.storage import bundle_metadata, fragments
from contextbridge.formation.providers.chat import parse_object
from contextbridge.models import CandidateProvenance, CaptureCandidate


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
    def __init__(self, legacy, client, sessions, settings):
        self.legacy, self.client, self.sessions, self.settings = legacy, client, sessions, settings

    def verify(self, candidate, event):
        with self.sessions() as session:
            metadata = bundle_metadata(session, self.settings.developer_id, event)
            row = session.scalar(
                select(CaptureCandidate).where(
                    CaptureCandidate.developer_id == self.settings.developer_id,
                    CaptureCandidate.candidate_id == UUID(candidate["candidate_id"]),
                )
            )
            extension = session.get(CandidateProvenance, row.id) if row and metadata else None
            if metadata is not None and (
                row is None or row.payload != candidate or extension is None
            ):
                raise ModuleError("INVALID_PROVIDER_OUTPUT")
            if extension is not None:
                parsed = CandidateMetadata.model_validate(extension.metadata_json)
                quotes = fragments(event, metadata["messages"], parsed.fragments)
        if metadata is None:
            return self.legacy.verify(candidate, event)
        if self.client is None:
            raise ModuleError("PROVIDER_UNAVAILABLE")
        raw = self.client.complete(
            self.client.settings.model,
            AUDIT,
            {
                "candidate": candidate,
                "original_event": event,
                "sources": metadata["messages"],
                "quoted_evidence": quotes,
                "temporal": parsed.temporal.model_dump(mode="json"),
            },
            Audit,
        )
        result = Audit.model_validate(parse_object(raw))
        conditions = {p.key: p.value for p in result.conditions}
        if len(conditions) != len(result.conditions) or result.scope != "bound":
            return "unsupported" if result.scope == "other" else "uncertain"
        if (
            result.kind != Candidate.model_validate(candidate).type
            or conditions != candidate["conditions"]
            or result.temporal_relation != parsed.temporal.relation
        ):
            return "uncertain"
        return result.support

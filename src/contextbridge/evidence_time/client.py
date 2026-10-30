"""Explicit bounded bundle import using the existing authenticated transcript transport."""

from pydantic import ValidationError

from contextbridge.capture_adapters.transcript import TranscriptClient
from contextbridge.contracts import IngestionResponse
from contextbridge.engine.errors import ModuleError
from contextbridge.evidence_time.contracts import EvidenceBundle
from contextbridge.security import contains_secret_fields


class BundleClient(TranscriptClient):
    def validate(self, payload):
        try:
            bundle = EvidenceBundle.model_validate(payload)
        except (ValidationError, TypeError, ValueError):
            raise ModuleError("INVALID_INPUT") from None
        first = bundle.events[0]
        if (first.scope == "project" and first.project_id != self.settings.project_id) or (
            first.scope == "developer" and not self.allow_developer
        ):
            raise ModuleError("OUT_OF_SCOPE")
        if contains_secret_fields(bundle.model_dump(mode="json")):
            raise ModuleError("INVALID_INPUT")
        return bundle

    def submit(self, payload):
        bundle = self.validate(payload)
        result = self.request(
            "POST", "/v2/interactions/bundles", IngestionResponse, bundle.model_dump(mode="json")
        )
        if result.event_id != bundle.bundle_id:
            raise ModuleError("INVALID_PROVIDER_OUTPUT")
        return result

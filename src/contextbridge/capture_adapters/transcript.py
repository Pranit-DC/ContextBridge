"""Bounded, opt-in transcript import; no host hooks, role guesses, or silent truncation."""

import json
from pathlib import Path
from uuid import UUID

import httpx
from pydantic import ValidationError

from contextbridge.contracts import CapturedEvent, IngestionResponse, JobResponse
from contextbridge.engine.errors import ModuleError
from contextbridge.formation.transcript import import_transcript

MAX_FILE_BYTES = 512 * 1024


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate field")
        result[key] = value
    return result


class TranscriptClient:
    def __init__(self, settings, *, allow_developer=False, transport=None):
        self.settings, self.allow_developer, self.transport = settings, allow_developer, transport

    def validate(self, payload):
        try:
            event = CapturedEvent.model_validate(payload)
            if event.capture_method != "manual_import":
                raise ModuleError("INVALID_INPUT")
            if (event.scope == "project" and event.project_id != self.settings.project_id) or (
                event.scope == "developer" and not self.allow_developer
            ):
                raise ModuleError("OUT_OF_SCOPE")
            normalized = import_transcript(
                **event.model_dump(exclude={"schema_version", "capture_method"})
            )
            return CapturedEvent.model_validate(normalized)
        except (ValidationError, TypeError, ValueError):
            raise ModuleError("INVALID_INPUT") from None

    def read(self, path: Path):
        try:
            with path.open("rb") as source:
                raw = source.read(MAX_FILE_BYTES + 1)
            if len(raw) > MAX_FILE_BYTES:
                raise ModuleError("INVALID_INPUT")
            return self.validate(json.loads(raw, object_pairs_hook=unique_fields))
        except (OSError, ValueError, UnicodeError, RecursionError):
            raise ModuleError("INVALID_INPUT") from None

    def request(self, method, path, model, body=None):
        try:
            with httpx.Client(
                base_url=str(self.settings.api_url),
                headers={"Authorization": f"Bearer {self.settings.api_token.get_secret_value()}"},
                timeout=self.settings.request_timeout,
                follow_redirects=False,
                trust_env=False,
                transport=self.transport,
            ) as client:
                response = client.request(method, path, json=body)
        except httpx.HTTPError:
            raise ModuleError("PROVIDER_UNAVAILABLE", retryable=True) from None
        status = response.status_code
        if status in {401, 403, 404}:
            raise ModuleError("OUT_OF_SCOPE")
        if status == 409:
            # A changed or cancelled replay is a conflict; no automatic retry is made.
            raise ModuleError("VERSION_CONFLICT")
        if status == 422:
            raise ModuleError("INVALID_INPUT")
        if status != (202 if method == "POST" else 200):
            raise ModuleError("PROVIDER_UNAVAILABLE", retryable=status >= 500)
        try:
            return model.model_validate(response.json())
        except (ValidationError, ValueError, TypeError):
            raise ModuleError("INVALID_PROVIDER_OUTPUT") from None

    def submit(self, payload):
        event = self.validate(payload)
        result = self.request(
            "POST", "/v1/interactions", IngestionResponse, event.model_dump(mode="json")
        )
        if result.event_id != event.event_id:
            raise ModuleError("INVALID_PROVIDER_OUTPUT")
        return result

    def status(self, job_id):
        try:
            job_id = UUID(str(job_id))
        except (TypeError, ValueError):
            raise ModuleError("INVALID_INPUT") from None
        result = self.request("GET", f"/v1/jobs/{job_id}", JobResponse)
        if result.job_id != job_id:
            raise ModuleError("INVALID_PROVIDER_OUTPUT")
        return result

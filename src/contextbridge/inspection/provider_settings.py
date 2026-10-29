"""Viewer-local settings boundary; the shared service owns credentials and persistence.

These are proposed client messages, not additions to the common HTTP contract. No default
implementation reads environment files, stages keys, writes settings or contacts providers.
"""

from typing import Literal, Protocol
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

GROQ_MODEL = "openai/gpt-oss-120b"
CLOUDFLARE_MODEL = "@cf/qwen/qwen3-embedding-0.6b"


class PublicMessage(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
        hide_input_in_errors=True,
        revalidate_instances="always",
    )


class ProviderSelection(PublicMessage):
    groq_provider: Literal["groq"] = "groq"
    groq_model: Literal["openai/gpt-oss-120b"] = GROQ_MODEL
    cloudflare_provider: Literal["cloudflare"] = "cloudflare"
    cloudflare_model: Literal["@cf/qwen/qwen3-embedding-0.6b"] = CLOUDFLARE_MODEL
    cloudflare_account_id: str = Field(default="", pattern=r"^(?:[0-9a-fA-F]{32})?$")


class SettingsSnapshot(ProviderSelection):
    revision: UUID
    groq_key_configured: bool = False
    cloudflare_key_configured: bool = False


class SettingsChange(ProviderSelection):
    expected_revision: UUID
    groq_key_action: Literal["keep", "replace", "remove"] = "keep"
    cloudflare_key_action: Literal["keep", "replace", "remove"] = "keep"


class CheckRequest(PublicMessage):
    expected_revision: UUID
    probe: Literal["supported-provider-connectivity-v1"] = "supported-provider-connectivity-v1"
    max_calls: Literal[2] = 2
    deadline_seconds: Literal[10] = 10
    max_output_tokens: Literal[32] = 32


Outcome = Literal[
    "ok",
    "authentication_failed",
    "timeout",
    "rate_limited",
    "unavailable",
    "invalid_response",
    "not_attempted",
]


class CheckReport(PublicMessage):
    checked_revision: UUID
    groq: Outcome
    cloudflare: Outcome
    calls: int = Field(ge=1, le=2)

    @model_validator(mode="after")
    def coherent_attempts(self):
        attempted = sum(status != "not_attempted" for status in (self.groq, self.cloudflare))
        if self.groq == "not_attempted" or self.calls != attempted:
            raise ValueError("Invalid check report")
        if self.groq != "ok" and self.cloudflare != "not_attempted":
            raise ValueError("Check must stop after the first failure")
        return self


VALIDATION_MESSAGES = {
    "missing_groq_key": "Groq key is missing. Stage and explicitly apply a service-side key.",
    "missing_cloudflare_key": (
        "Cloudflare key is missing. Stage and explicitly apply a service-side key."
    ),
    "missing_account": "Cloudflare account ID is missing (32 hexadecimal characters required).",
}


def validate_settings(snapshot: SettingsSnapshot) -> list[str]:
    """Deterministic public configuration checks; no network, key reads or writes."""
    snapshot = SettingsSnapshot.model_validate(snapshot)
    missing = []
    if not snapshot.groq_key_configured:
        missing.append("missing_groq_key")
    if not snapshot.cloudflare_key_configured:
        missing.append("missing_cloudflare_key")
    if not snapshot.cloudflare_account_id:
        missing.append("missing_account")
    return missing


class SettingsClient(Protocol):
    """Inject an owner-provided, authorized local service client, never a credential store.

    Replacement consumes a service-staged key for this local operator atomically. A revision
    conflict must change nothing. Keys and key fragments never appear in these messages.
    """

    def read(self) -> SettingsSnapshot: ...

    def apply(self, change: SettingsChange) -> SettingsSnapshot: ...

    def check(self, request: CheckRequest) -> CheckReport:
        """One overall 10s deadline; two requests maximum; no retries/redirects/proxies.

        Send only the documented fixed synthetic probe. Stop on the first failure and
        validate expected_revision before reading credentials. No memory/database reads.
        """
        ...


ERRORS = {
    "pending": "Shared service settings integration is pending. No configuration was changed.",
    "unavailable": "Settings service unavailable. Your draft is preserved; reload before retrying.",
    "conflict": "Settings changed elsewhere. Reload and review before applying your draft.",
    "invalid": "Check the supported models and Cloudflare account ID (32 hexadecimal characters).",
    "replacement_missing": "Stage a replacement key privately in the service before applying it.",
    "unauthorized": "Settings access was rejected. Check the ContextBridge access token.",
    "consent_required": "Confirm the data and quota implications before starting an online check.",
    "incomplete": "Provider configuration is incomplete. Validate the saved settings first.",
    "timeout": "Connection check timed out. It was not retried; review before checking again.",
}


class SettingsError(Exception):
    def __init__(self, code: str):
        self.code = code if code in ERRORS else "unavailable"
        super().__init__(ERRORS[self.code])


class PendingSettingsClient:
    def read(self):
        raise SettingsError("pending")

    def apply(self, change):
        raise SettingsError("pending")

    def check(self, request):
        raise SettingsError("pending")


class SettingsController:
    def __init__(self, client: SettingsClient):
        self.client = client

    def read(self) -> SettingsSnapshot:
        return self._call(self.client.read)

    def apply(self, change: SettingsChange, *, confirmed: bool) -> SettingsSnapshot:
        if not confirmed:
            raise SettingsError("invalid")
        # Revalidate model instances too: model_construct/model_copy may bypass validation.
        code = None
        try:
            change = SettingsChange.model_validate(change)
        except Exception:
            code = "invalid"
        if code:
            raise SettingsError(code) from None
        return self._call(lambda: self.client.apply(change))

    def check(self, snapshot: SettingsSnapshot, *, consent: bool) -> CheckReport:
        if not consent:
            raise SettingsError("consent_required")
        if validate_settings(snapshot):
            raise SettingsError("incomplete")
        report = self._call(
            lambda: self.client.check(CheckRequest(expected_revision=snapshot.revision)),
            CheckReport,
        )
        if report.checked_revision != snapshot.revision:
            raise SettingsError("conflict")
        return report

    @staticmethod
    def _call(operation, model=SettingsSnapshot):
        # The injected client may fail with an HTTP body/key in its exception. Never
        # render, log or chain that exception into Streamlit's exception display.
        code = None
        try:
            result = operation()
            return model.model_validate(result)
        except SettingsError as error:
            code = error.code
        except httpx.TimeoutException:
            code = "timeout"
        except httpx.HTTPStatusError as error:
            code = "unauthorized" if error.response.status_code in (401, 403) else "unavailable"
        except Exception:
            code = "unavailable"
        raise SettingsError(code) from None

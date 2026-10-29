"""Viewer-local settings boundary; the shared service owns credentials and persistence.

These are proposed client messages, not additions to the common HTTP contract. No default
implementation reads environment files, stages keys, writes settings or contacts providers.
"""

from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

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


class SettingsClient(Protocol):
    """Inject an owner-provided, authorized local service client, never a credential store.

    Replacement consumes a service-staged key for this local operator atomically. A revision
    conflict must change nothing. Keys and key fragments never appear in these messages.
    """

    def read(self) -> SettingsSnapshot: ...

    def apply(self, change: SettingsChange) -> SettingsSnapshot: ...


ERRORS = {
    "pending": "Shared service settings integration is pending. No configuration was changed.",
    "unavailable": "Settings service unavailable. Your draft is preserved; reload before retrying.",
    "conflict": "Settings changed elsewhere. Reload and review before applying your draft.",
    "invalid": "Check the supported models and Cloudflare account ID (32 hexadecimal characters).",
    "replacement_missing": "Stage a replacement key privately in the service before applying it.",
    "unauthorized": "Settings access was rejected. Check the ContextBridge access token.",
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

    @staticmethod
    def _call(operation):
        # The injected client may fail with an HTTP body/key in its exception. Never
        # render, log or chain that exception into Streamlit's exception display.
        code = None
        try:
            result = operation()
            return SettingsSnapshot.model_validate(result)
        except SettingsError as error:
            code = error.code
        except Exception:
            code = "unavailable"
        raise SettingsError(code) from None

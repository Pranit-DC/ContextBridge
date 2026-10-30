"""Opt-in, per-installation formation configuration; no shared service settings."""

import ipaddress
import re
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from contextbridge.engine.errors import ModuleError
from contextbridge.security import contains_secret

DEFAULT_ENDPOINTS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "ollama": "http://127.0.0.1:11434/v1",
}
GROQ_ENDPOINT = "https://api.groq.com/openai/v1"
GROQ_FREE_MODELS = frozenset(("openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"))


def is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class FormationSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CONTEXTBRIDGE_FORMATION_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        hide_input_in_errors=True,
    )

    provider: Literal["openrouter", "openai-compatible", "ollama"]
    model: str = Field(min_length=1, max_length=128)
    verifier_model: str | None = Field(default=None, min_length=1, max_length=128)
    api_key: SecretStr | None = Field(default=None, repr=False, exclude=True)
    base_url: str | None = Field(default=None, max_length=512)
    timeout_seconds: float = Field(default=30, ge=1, le=120, allow_inf_nan=False)
    max_output_tokens: int = Field(default=8192, ge=128, le=16384)
    response_format: Literal["json_schema", "json_object"] = "json_schema"
    allow_hosted: bool = False
    allow_paid: bool = False
    openrouter_free_only: bool = True
    openrouter_data_collection: Literal["deny", "allow"] = "deny"
    # Operator attestation, not an API-verified billing guarantee. Default remains blocked.
    groq_free_plan_confirmed: bool = False
    groq_reasoning_effort: Literal["low", "medium", "high"] = "low"

    @field_validator("model", "verifier_model")
    @classmethod
    def safe_model(cls, value):
        if value is not None and (
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", value) or contains_secret(value)
        ):
            raise ValueError("Invalid model identifier")
        return value

    @field_validator("api_key", mode="before")
    @classmethod
    def empty_key(cls, value):
        return None if value == "" else value

    @field_validator("api_key")
    @classmethod
    def safe_key(cls, value):
        if value is not None:
            key = value.get_secret_value()
            if not 12 <= len(key) <= 4096 or any(ord(char) < 33 or ord(char) > 126 for char in key):
                raise ValueError("Invalid API key")
        return value

    @model_validator(mode="after")
    def endpoint(self):
        endpoint = self.base_url or DEFAULT_ENDPOINTS.get(self.provider)
        if endpoint is None:
            raise ValueError("An explicit compatible endpoint is required")
        try:
            url = urlsplit(endpoint)
            # Validate port syntax even though it is not printed separately.
            port = url.port
        except ValueError:
            raise ValueError("Invalid endpoint") from None
        if (
            not url.hostname
            or url.username is not None
            or url.password is not None
            or url.query
            or url.fragment
            or contains_secret(endpoint)
            or any(ord(char) < 33 or ord(char) > 126 for char in endpoint)
            or "\\" in endpoint
            or port == 0
            or url.scheme not in ("http", "https")
            or (url.scheme == "http" and not is_loopback(url.hostname))
        ):
            raise ValueError("Use HTTPS, or loopback HTTP, without URL credentials")
        endpoint = endpoint.rstrip("/")
        if self.provider == "openrouter" and endpoint != DEFAULT_ENDPOINTS["openrouter"]:
            raise ValueError("OpenRouter requires its official endpoint")
        if self.provider == "ollama" and not is_loopback(url.hostname):
            raise ValueError("Ollama is a local provider")
        if not is_loopback(url.hostname) and self.api_key is None:
            raise ValueError("Hosted endpoints require an API key")
        if self.provider == "openrouter" and self.api_key is None:
            raise ValueError("OpenRouter requires an API key")
        models = (self.model, self.verifier_model or self.model)
        if self.api_key is not None:
            key = self.api_key.get_secret_value()
            if any(key in value for value in (*models, endpoint)):
                raise ValueError("Credentials cannot appear in public configuration")
        if self.provider == "openrouter" and self.openrouter_free_only:
            if any(not model.endswith(":free") or model == "openrouter/free" for model in models):
                raise ValueError("Select explicit free model IDs for extraction and verification")
        object.__setattr__(self, "base_url", endpoint)
        return self

    def check_execution(self):
        hosted = not is_loopback(urlsplit(self.base_url).hostname)
        if hosted and not self.allow_hosted:
            raise ModuleError("INVALID_INPUT")
        assured_free = (
            self.provider == "openrouter" and self.openrouter_free_only
        ) or self.is_groq_free()
        if hosted and not assured_free and not self.allow_paid:
            raise ModuleError("INVALID_INPUT")

    def is_groq_free(self):
        return (
            self.provider == "openai-compatible"
            and self.base_url == GROQ_ENDPOINT
            and self.groq_free_plan_confirmed
            and not self.allow_paid
            and all(
                model in GROQ_FREE_MODELS
                for model in (self.model, self.verifier_model or self.model)
            )
        )

    def public_configuration(self) -> dict:
        public = {
            "provider": self.provider,
            "model": self.model,
            "verifier_model": self.verifier_model or self.model,
            "base_url": self.base_url,
            "api_key_configured": self.api_key is not None,
            "timeout_seconds": self.timeout_seconds,
            "max_output_tokens": self.max_output_tokens,
            "response_format": self.response_format,
            "allow_hosted": self.allow_hosted,
            "allow_paid": self.allow_paid,
            "openrouter_free_only": self.openrouter_free_only,
            "openrouter_data_collection": self.openrouter_data_collection,
        }
        if self.base_url == GROQ_ENDPOINT:
            public.update(
                groq_free_plan_confirmed=self.groq_free_plan_confirmed,
                groq_reasoning_effort=self.groq_reasoning_effort,
            )
        return public


def load_settings(env_file: str | Path = ".env") -> FormationSettings:
    """Environment variables override the local file; sanitize every configuration failure."""
    try:
        from contextbridge.product.bootstrap import managed_enabled, read_credentials

        if managed_enabled():
            return FormationSettings(_env_file=env_file, api_key=read_credentials()["groq"])
        return FormationSettings(_env_file=env_file)
    except Exception:
        raise ModuleError("INVALID_INPUT") from None

"""Authorized service-side provider configuration, separate from memory persistence."""

import argparse
import getpass
import hashlib
import hmac
import json
import sys
import time
from typing import Literal
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from contextbridge.inspection.provider_settings import (
    CLOUDFLARE_MODEL,
    GROQ_MODEL,
    CheckReport,
    SettingsChange,
    SettingsError,
    SettingsSnapshot,
)
from contextbridge.provider_files import (
    atomic_write,
    check_private,
    checked_path,
    configuration_lock,
)


def validate_key(value):
    if value is not None:
        key = value.get_secret_value()
        if not 12 <= len(key) <= 4096 or any(not 33 <= ord(c) <= 126 for c in key):
            raise ValueError("Invalid provider credential")
    return value


class PrivateConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)
    schema_version: Literal[1] = 1
    owner: str = Field(min_length=1, max_length=128)
    revision: UUID = UUID(int=0)
    cloudflare_account_id: str = Field(default="", pattern=r"^(?:[0-9a-fA-F]{32})?$")
    groq_key: SecretStr | None = Field(default=None, repr=False, exclude=True)
    cloudflare_key: SecretStr | None = Field(default=None, repr=False, exclude=True)
    staged_groq: SecretStr | None = Field(default=None, repr=False, exclude=True)
    staged_cloudflare: SecretStr | None = Field(default=None, repr=False, exclude=True)
    staged_revision: UUID | None = None
    staged_binding: str | None = Field(default=None, repr=False, exclude=True)

    _keys = field_validator("groq_key", "cloudflare_key", "staged_groq", "staged_cloudflare")(
        validate_key
    )


class ProviderConfiguration:
    def __init__(self, settings):
        self.settings = settings
        if settings.provider_settings_file is None:
            raise SettingsError("not_configured")
        self.path = checked_path(settings.provider_settings_file)

    def private(self):
        if not self.path.exists():
            return PrivateConfiguration(owner=self.settings.developer_id)
        code = None
        try:
            check_private(self.path.parent)
            check_private(self.path)
            if self.path.stat().st_size > 65_536:
                raise SettingsError("invalid")
            record = PrivateConfiguration.model_validate_json(self.path.read_bytes())
            if record.schema_version != 1:
                raise SettingsError("invalid")
            if record.owner != self.settings.developer_id:
                raise SettingsError("unauthorized")
            return record
        except SettingsError as error:
            code = error.code
        except Exception:
            code = "invalid"
        raise SettingsError(code) from None

    @staticmethod
    def snapshot(record):
        return SettingsSnapshot(
            revision=record.revision,
            cloudflare_account_id=record.cloudflare_account_id,
            groq_key_configured=record.groq_key is not None,
            cloudflare_key_configured=record.cloudflare_key is not None,
        )

    def read(self):
        return self.snapshot(self.private())

    def _binding(self, revision):
        return hmac.new(
            self.settings.api_token.get_secret_value().encode(),
            f"{self.settings.developer_id}\0{revision}".encode(),
            hashlib.sha256,
        ).hexdigest()

    def _write(self, record):
        data = record.model_dump(mode="json")
        for name in ("groq_key", "cloudflare_key", "staged_groq", "staged_cloudflare"):
            value = getattr(record, name)
            data[name] = value.get_secret_value() if value else None
        data["staged_binding"] = record.staged_binding
        atomic_write(self.path, json.dumps(data, separators=(",", ":")).encode())

    def stage(self, provider, credential: SecretStr, expected_revision):
        if provider not in ("groq", "cloudflare"):
            raise SettingsError("invalid")
        code = None
        try:
            validate_key(credential)
            if hmac.compare_digest(
                credential.get_secret_value(), self.settings.api_token.get_secret_value()
            ):
                raise ValueError
        except Exception:
            code = "invalid"
        if code:
            raise SettingsError(code) from None
        with configuration_lock(self.path):
            record = self.private()
            if record.revision != expected_revision:
                raise SettingsError("conflict")
            changes = {
                f"staged_{provider}": credential,
                "staged_revision": record.revision,
                "staged_binding": self._binding(record.revision),
            }
            if record.staged_binding != self._binding(record.revision):
                changes[f"staged_{'cloudflare' if provider == 'groq' else 'groq'}"] = None
            self._write(record.model_copy(update=changes))

    def apply(self, change):
        change = SettingsChange.model_validate(change)
        with configuration_lock(self.path):
            record = self.private()
            if record.revision != change.expected_revision:
                raise SettingsError("conflict")
            updates = {
                "revision": uuid4(),
                "cloudflare_account_id": change.cloudflare_account_id,
                "staged_groq": None,
                "staged_cloudflare": None,
                "staged_binding": None,
                "staged_revision": None,
            }
            for provider in ("groq", "cloudflare"):
                action = getattr(change, f"{provider}_key_action")
                if action == "remove":
                    updates[f"{provider}_key"] = None
                elif action == "replace":
                    staged = getattr(record, f"staged_{provider}")
                    if (
                        staged is None
                        or record.staged_revision != record.revision
                        or record.staged_binding != self._binding(record.revision)
                    ):
                        raise SettingsError("replacement_missing")
                    updates[f"{provider}_key"] = staged
            updated = record.model_copy(update=updates)
            self._write(updated)
            return self.snapshot(updated)

    def check(self, request):
        from contextbridge.inspection.provider_settings import CheckRequest
        from contextbridge.provider_probe import execute_probe

        request = CheckRequest.model_validate(request)
        deadline = time.monotonic() + request.deadline_seconds
        with configuration_lock(self.path, deadline=deadline):
            record = self.private()
            if record.revision != request.expected_revision:
                raise SettingsError("conflict")
            if not (record.groq_key and record.cloudflare_key and record.cloudflare_account_id):
                raise SettingsError("incomplete")
            formation = formation_settings(record)
            if (
                not formation.allow_hosted
                or not formation.groq_free_plan_confirmed
                or formation.allow_paid
            ):
                raise SettingsError("policy_blocked")
            report = execute_probe(record, deadline=deadline)
            return CheckReport(checked_revision=record.revision, **report)


def formation_settings(record):
    from contextbridge.formation.providers.config import FormationSettings

    return FormationSettings(
        provider="openai-compatible",
        model=GROQ_MODEL,
        verifier_model=GROQ_MODEL,
        base_url="https://api.groq.com/openai/v1",
        api_key=record.groq_key,
    )


def effective_configuration(settings):
    if settings.provider_settings_file is None:
        return settings, None
    record = ProviderConfiguration(settings).private()
    formation = settings.formation_enabled and record.groq_key is not None
    if formation:
        policy = formation_settings(record)
        formation = policy.allow_hosted and policy.is_groq_free()
    embedding = record.cloudflare_key is not None and bool(record.cloudflare_account_id)
    return settings.model_copy(
        update={
            "formation_enabled": formation,
            "consolidation_enabled": settings.consolidation_enabled and formation,
            "embedding_provider": "cloudflare" if embedding else None,
            "embedding_api_key": record.cloudflare_key,
            "embedding_base_url": SecretStr(
                f"https://api.cloudflare.com/client/v4/accounts/{record.cloudflare_account_id}/ai/v1"
            )
            if embedding
            else None,
            "embedding_model_id": CLOUDFLARE_MODEL if embedding else None,
            "embedding_dimensions": 1024 if embedding else None,
        }
    ), record


def runtime_metadata(settings):
    effective, _ = effective_configuration(settings)
    if settings.provider_settings_file is not None:
        effective = effective.model_copy(
            update={"embedding_api_key": None, "embedding_base_url": None}
        )
    return effective


class ConfigurationTransport(httpx.BaseTransport):
    """Fence stale credentials at the final network boundary, including quota waits."""

    def __init__(self, settings, revision, transport=None):
        self.settings, self.revision = settings, revision
        self.transport = transport or httpx.HTTPTransport(retries=0, trust_env=False)

    def handle_request(self, request):
        from contextbridge.engine.errors import ModuleError

        store = ProviderConfiguration(self.settings)
        try:
            with configuration_lock(store.path):
                if store.private().revision != self.revision:
                    raise SettingsError("conflict")
                return self.transport.handle_request(request)
        except SettingsError:
            pass
        raise ModuleError("PROVIDER_UNAVAILABLE", retryable=False) from None

    def close(self):
        self.transport.close()


def main():
    from contextbridge.config import Settings

    class SafeParser(argparse.ArgumentParser):
        def error(self, message):
            self.exit(2, "Invalid provider staging arguments.\n")

    parser = SafeParser(description="Private service-side provider key staging")
    parser.add_argument("action", choices=("show", "stage"))
    parser.add_argument("--provider", choices=("groq", "cloudflare"))
    parser.add_argument("--expected-revision", type=UUID)
    args = parser.parse_args()
    try:
        service = ProviderConfiguration(Settings())
        if args.action == "show":
            print(service.read().model_dump_json())
        else:
            if not sys.stdin.isatty():
                raise SettingsError("invalid")
            if not args.provider or args.expected_revision is None:
                raise SettingsError("invalid")
            service.stage(
                args.provider,
                SecretStr(getpass.getpass("Provider key (hidden): ")),
                args.expected_revision,
            )
            print("Replacement staged privately. Apply it explicitly in Provider setup.")
        return 0
    except Exception:
        print(
            "Provider configuration operation failed. Check service settings and revision.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

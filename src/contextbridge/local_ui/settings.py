"""Private, optimistic, atomic dotenv edits. No secrets in public snapshots or errors."""

import hashlib
import io
import json
import os
import re
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv.parser import parse_stream
from pydantic import Field, SecretStr, field_validator

from contextbridge.config import Settings
from contextbridge.formation.providers.config import (
    GROQ_ENDPOINT,
    GROQ_FREE_MODELS,
    FormationSettings,
)
from contextbridge.retrieval.cloudflare import DIMENSIONS, MODEL_ID, valid_base_url
from contextbridge.schemas import Identifier, StrictModel
from contextbridge.security import contains_secret

PREFIX = "CONTEXTBRIDGE_"
GROQ_KEY = PREFIX + "FORMATION_API_KEY"
CLOUD_KEY = PREFIX + "EMBEDDING_API_KEY"


class SettingsError(Exception):
    """Only fixed messages cross the local UI boundary."""


class Preferences(StrictModel):
    project: Identifier = "contextbridge"
    processing: bool = False
    meaning_search: bool = False
    groq_model: str = "openai/gpt-oss-120b"
    groq_free_confirmed: bool = False
    cloudflare_account: str = ""
    grouping: bool = False
    evidence_v2: bool = False
    idle_seconds: int = Field(default=30, ge=1, le=300)
    group_events: int = Field(default=5, ge=1, le=20)
    retention_seconds: int = Field(default=86_400, ge=60, le=2_592_000)
    consolidation: bool = False
    daily_tokens: int = Field(default=50_000, ge=128, le=50_000)

    @field_validator("groq_model")
    @classmethod
    def model(cls, value):
        if value not in GROQ_FREE_MODELS:
            raise ValueError("Choose a supported model")
        return value

    @field_validator("cloudflare_account")
    @classmethod
    def account(cls, value):
        if value and not re.fullmatch(r"[0-9a-fA-F]{32}", value):
            raise ValueError("Enter the 32-character Cloudflare account ID")
        return value

    @field_validator("project")
    @classmethod
    def safe_project(cls, value):
        if contains_secret(value) or any(ord(c) < 32 for c in value):
            raise ValueError("Use a project name without credentials")
        return value


class KeyChange(StrictModel):
    action: Literal["keep", "replace", "remove"] = "keep"
    value: SecretStr | None = Field(default=None, repr=False, exclude=True)

    def replacement(self, current):
        if self.action == "remove":
            return None
        value = self.value.get_secret_value() if self.value is not None else ""
        if self.action == "replace":
            if not re.fullmatch(r"[A-Za-z0-9._-]{12,4096}", value):
                raise SettingsError("Enter a valid provider key without spaces or line breaks.")
            return value
        if value:
            raise SettingsError("Choose Replace key before entering a new key.")
        if current and not re.fullmatch(r"[A-Za-z0-9._-]{12,4096}", current):
            raise SettingsError(
                "The saved key uses an unsupported format. Replace or remove it before saving."
            )
        return current or None


@dataclass(frozen=True)
class Snapshot:
    revision: str
    preferences: Preferences
    groq_key_configured: bool
    cloudflare_key_configured: bool
    custom_runtime: bool


class FileSettings(Settings):
    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, *args, **kwargs):
        return (init_settings,)


class FileFormation(FormationSettings):
    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, *args, **kwargs):
        return (init_settings,)


def validate_runtime(values):
    """Validate the proposed file alone; stale shell credentials never override it."""
    try:
        config = FileSettings(
            **{
                name: values[PREFIX + name.upper()]
                for name in FileSettings.model_fields
                if PREFIX + name.upper() in values
            }
        )
        if config.formation_enabled:
            formation = FileFormation(
                **{
                    name: values[PREFIX + "FORMATION_" + name.upper()]
                    for name in FileFormation.model_fields
                    if PREFIX + "FORMATION_" + name.upper() in values
                }
            )
            formation.check_execution()
    except Exception:
        raise SettingsError(
            "Configuration is incomplete. Check provider keys, model and local setup."
        ) from None


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class SettingsStore:
    def __init__(self, path):
        # The launcher fixes this path; it is never supplied by a browser form.
        self.path = Path(path).absolute()
        self.state = self.path.parent / ".contextbridge"

    def read(self):
        if self.path.is_symlink() or not self.path.is_file():
            raise SettingsError("Local settings are unavailable. Run the setup launcher first.")
        try:
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            with os.fdopen(os.open(self.path, flags), "rb") as file:
                raw = file.read(131_073)
            if len(raw) > 131_072:
                raise ValueError
            bindings = list(parse_stream(io.StringIO(raw.decode("utf-8-sig"))))
            if any(binding.error for binding in bindings):
                raise ValueError
            values = {b.key: b.value or "" for b in bindings if b.key is not None}
            return raw, bindings, values
        except (OSError, ValueError, UnicodeError):
            raise SettingsError("The local settings file cannot be read safely.") from None

    @contextmanager
    def lock(self):
        if self.state.is_symlink():
            raise SettingsError("The local settings folder cannot be used safely.")
        self.state.mkdir(mode=0o700, exist_ok=True)
        path = self.state / "settings.lock"
        if path.is_symlink():
            raise SettingsError("The local settings lock cannot be used safely.")
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(descriptor, "r+b") as file:
            try:
                if os.name == "nt":
                    import msvcrt

                    if file.seek(0, 2) == 0:
                        file.write(b"0")
                        file.flush()
                    file.seek(0)
                    msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise SettingsError("Settings are being changed. Try again shortly.") from None
            try:
                yield
            finally:
                if os.name == "nt":
                    file.seek(0)
                    msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(file.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def preferences(values):
        def value(name, default=""):
            return values.get(PREFIX + name, default)

        base = value("EMBEDDING_BASE_URL")
        account = base.split("/accounts/")[1].split("/")[0] if valid_base_url(base) else ""
        try:
            return Preferences(
                project=value("CAPTURE_PROJECT_ID", "contextbridge") or "contextbridge",
                processing=value("FORMATION_ENABLED", "false"),
                meaning_search=value("EMBEDDING_PROVIDER") == "cloudflare",
                groq_model=value("FORMATION_MODEL", "openai/gpt-oss-120b") or "openai/gpt-oss-120b",
                groq_free_confirmed=value("FORMATION_GROQ_FREE_PLAN_CONFIRMED", "false"),
                cloudflare_account=account,
                grouping=value("CAPTURE_GROUPING_ENABLED", "false"),
                evidence_v2=value("CAPTURE_EVIDENCE_V2_ENABLED", "false"),
                idle_seconds=value("CAPTURE_GROUP_IDLE_SECONDS", "30"),
                group_events=value("CAPTURE_GROUP_MAX_EVENTS", "5"),
                retention_seconds=value("CAPTURE_RETENTION_SECONDS", "86400"),
                consolidation=value("CONSOLIDATION_ENABLED", "false"),
                daily_tokens=value("FORMATION_TOKENS_PER_DAY", "50000"),
            )
        except (ValueError, TypeError):
            raise SettingsError(
                "Some saved options need review before using this settings panel."
            ) from None

    def snapshot(self):
        raw, _, values = self.read()
        prefs = self.preferences(values)
        # A custom factory/provider cannot silently be replaced by this supported-stack panel.
        custom = any(
            values.get(PREFIX + name) for name in ("INTEGRATION_FACTORY", "WORKER_FACTORY")
        )
        custom = (
            custom
            or values.get(PREFIX + "FORMATION_PROVIDER", "") not in ("", "openai-compatible")
            or values.get(PREFIX + "FORMATION_BASE_URL", "") not in ("", GROQ_ENDPOINT)
        )
        custom = custom or values.get(PREFIX + "EMBEDDING_PROVIDER", "") not in ("", "cloudflare")
        public = json.dumps(prefs.model_dump())
        if any(values.get(key) and values[key] in public for key in (GROQ_KEY, CLOUD_KEY)):
            raise SettingsError("Credentials must be separate from public settings.")
        return Snapshot(
            digest(raw),
            prefs,
            bool(values.get(GROQ_KEY)),
            bool(values.get(CLOUD_KEY)),
            bool(custom),
        )

    def replace(self, content):
        """Atomic private replacement, no backup or hidden copy of removed credentials."""
        temporary = None
        try:
            descriptor, temporary = tempfile.mkstemp(prefix=".settings-", dir=self.path.parent)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    def save(self, revision, preferences, groq=None, cloudflare=None):
        with self.lock():
            raw, bindings, values = self.read()
            if digest(raw) != revision:
                raise SettingsError("Settings changed in another window. Reload before saving.")
            if self.snapshot().custom_runtime:
                raise SettingsError("Custom providers are managed outside this settings panel.")
            prefs = Preferences.model_validate(preferences)
            groq_key = (groq or KeyChange()).replacement(values.get(GROQ_KEY))
            cloud_key = (cloudflare or KeyChange()).replacement(values.get(CLOUD_KEY))
            if prefs.processing and not groq_key and (groq or KeyChange()).action != "remove":
                raise SettingsError("Add a Groq key before enabling processing.")
            if (
                prefs.meaning_search
                and not cloud_key
                and (cloudflare or KeyChange()).action != "remove"
            ):
                raise SettingsError("Add a Cloudflare token before enabling meaning search.")
            prefs = prefs.model_copy(
                update={
                    "processing": prefs.processing and groq_key is not None,
                    "meaning_search": prefs.meaning_search and cloud_key is not None,
                }
            )
            if prefs.processing and not prefs.groq_free_confirmed:
                raise SettingsError("Confirm your Groq Free plan before enabling processing.")
            if prefs.meaning_search and not prefs.cloudflare_account:
                raise SettingsError(
                    "Enter the Cloudflare account ID before enabling meaning search."
                )
            if any(key and key in json.dumps(prefs.model_dump()) for key in (groq_key, cloud_key)):
                raise SettingsError("Credentials must be separate from public settings.")
            updates = {
                "CAPTURE_PROJECT_ID": prefs.project,
                "FORMATION_ENABLED": prefs.processing,
                "FORMATION_PROVIDER": "openai-compatible",
                "FORMATION_BASE_URL": GROQ_ENDPOINT,
                "FORMATION_MODEL": prefs.groq_model,
                "FORMATION_VERIFIER_MODEL": prefs.groq_model,
                "FORMATION_API_KEY": groq_key,
                "FORMATION_ALLOW_HOSTED": prefs.processing,
                "FORMATION_ALLOW_PAID": False,
                "FORMATION_GROQ_FREE_PLAN_CONFIRMED": prefs.groq_free_confirmed,
                "FORMATION_MAX_OUTPUT_TOKENS": values.get(
                    PREFIX + "FORMATION_MAX_OUTPUT_TOKENS", "1024"
                ),
                "FORMATION_TOKENS_PER_DAY": prefs.daily_tokens,
                "EMBEDDING_PROVIDER": "cloudflare" if prefs.meaning_search else None,
                "EMBEDDING_API_KEY": cloud_key,
                "EMBEDDING_BASE_URL": f"https://api.cloudflare.com/client/v4/accounts/{prefs.cloudflare_account}/ai/v1"
                if prefs.cloudflare_account
                else None,
                "EMBEDDING_MODEL_ID": MODEL_ID if prefs.meaning_search else None,
                "EMBEDDING_DIMENSIONS": DIMENSIONS if prefs.meaning_search else None,
                "CAPTURE_GROUPING_ENABLED": prefs.grouping,
                "CAPTURE_EVIDENCE_V2_ENABLED": prefs.evidence_v2,
                "CAPTURE_GROUP_IDLE_SECONDS": prefs.idle_seconds,
                "CAPTURE_GROUP_MAX_EVENTS": prefs.group_events,
                "CAPTURE_RETENTION_SECONDS": prefs.retention_seconds,
                "CONSOLIDATION_ENABLED": prefs.consolidation and prefs.processing,
            }
            updates = {PREFIX + key: value for key, value in updates.items()}
            proposed = {
                key: str(value).lower() if isinstance(value, bool) else str(value)
                for key, value in {**values, **updates}.items()
                if value is not None
            }
            validate_runtime(proposed)

            def line(key):
                value = updates[key]
                if value is None:
                    return ""
                if isinstance(value, bool):
                    value = str(value).lower()
                value = str(value).replace("\\", "\\\\").replace("'", "\\'")
                return f"{key}='{value}'\n"

            seen, output = set(), []
            for binding in bindings:
                if binding.key in updates:
                    if binding.key not in seen:
                        output.append(line(binding.key))
                        seen.add(binding.key)
                else:
                    output.append(binding.original.string)
            if output and not output[-1].endswith("\n"):
                output.append("\n")
            output.extend(line(key) for key in updates if key not in seen)
            # Detect external edits that do not participate in the advisory lock.
            if self.read()[0] != raw:
                raise SettingsError("Settings changed. Reload before saving.")
            self.replace("".join(output))
        return self.snapshot()

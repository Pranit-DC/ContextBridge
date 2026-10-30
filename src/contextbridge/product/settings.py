"""Reuse legacy validation in memory; persist provider keys only in the native vault."""

import io
from uuid import uuid4

from dotenv.parser import parse_stream

from contextbridge.local_ui.settings import (
    CLOUD_KEY,
    GROQ_KEY,
    KeyChange,
    Preferences,
    SettingsError,
    SettingsStore,
    digest,
)
from contextbridge.product.vault import NativeVault, VaultRecord

MARKER = "CONTEXTBRIDGE_MANAGED_CREDENTIALS"


class MemorySettings(SettingsStore):
    def __init__(self, legacy, raw):
        super().__init__(legacy.path)
        self.legacy, self.raw = legacy, raw

    def read(self):
        bindings = list(parse_stream(io.StringIO(self.raw.decode("utf-8"))))
        return self.raw, bindings, {b.key: b.value or "" for b in bindings if b.key}

    def replace(self, content):
        self.raw = content.encode()

    def lock(self):
        return self.legacy.lock()


def private_raw(raw, *, keys=None, managed=False):
    bindings = list(parse_stream(io.StringIO(raw.decode("utf-8-sig"))))
    if any(b.error for b in bindings):
        raise SettingsError("Local settings need review.")
    kept = "".join(
        b.original.string for b in bindings if b.key not in (GROQ_KEY, CLOUD_KEY, MARKER)
    )
    if kept and not kept.endswith("\n"):
        kept += "\n"
    if keys:
        for name, value in ((GROQ_KEY, keys.groq), (CLOUD_KEY, keys.cloudflare)):
            if value:
                kept += f"{name}='{value}'\n"
    if managed:
        kept += f"{MARKER}='true'\n"
    return kept.encode()


class ProductSettings:
    def __init__(self, path, *, vault=None):
        self.legacy = SettingsStore(path)
        self.vault = vault or NativeVault(self.legacy.path.parent)

    def record(self):
        stored = self.vault.read()
        return stored or VaultRecord(
            revision="initial", preferences=self.legacy.snapshot().preferences
        )

    def public(self):
        raw, _, values = self.legacy.read()
        base = {
            "legacy_keys_present": bool(values.get(GROQ_KEY) or values.get(CLOUD_KEY)),
            "managed": values.get(MARKER) == "true",
            "file_revision": digest(raw),
        }
        try:
            record = self.record()
            return base | record.public() | {"storage_available": True}
        except SettingsError as error:
            return base | {
                "storage_available": False,
                "message": str(error),
                "revision": "locked",
                "preferences": Preferences().model_dump(),
                "groq_configured": False,
                "cloudflare_configured": False,
            }

    def runtime(self, record=None):
        record = record or self.record()
        raw, _, _ = self.legacy.read()
        memory = MemorySettings(self.legacy, private_raw(raw, keys=record))
        memory.save(memory.snapshot().revision, record.preferences)
        return memory

    def save(self, revision, preferences, groq, cloudflare):
        with self.legacy.lock():
            current = self.record()
            existing_values = self.legacy.read()[2]
            if existing_values.get(GROQ_KEY) or existing_values.get(CLOUD_KEY):
                raise SettingsError("Migrate existing provider keys before saving secure settings.")
            if current.revision != revision:
                raise SettingsError("Settings changed. Reload before saving.")
            if self.legacy.snapshot().custom_runtime:
                raise SettingsError("Custom providers are managed outside this workspace.")
            next_record = VaultRecord(
                str(uuid4()),
                Preferences.model_validate(preferences),
                KeyChange.model_validate(groq).replacement(current.groq),
                KeyChange.model_validate(cloudflare).replacement(current.cloudflare),
            )
            next_record.preferences = next_record.preferences.model_copy(
                update={
                    "processing": next_record.preferences.processing
                    and next_record.groq is not None,
                    "meaning_search": next_record.preferences.meaning_search
                    and next_record.cloudflare is not None,
                    "consolidation": next_record.preferences.consolidation
                    and next_record.groq is not None,
                }
            )
            # Validation uses an in-memory store and must not acquire the same lock twice.
            from contextlib import nullcontext

            memory = MemorySettings(
                self.legacy, private_raw(self.legacy.read()[0], keys=next_record)
            )
            memory.lock = nullcontext
            memory.save(
                memory.snapshot().revision,
                next_record.preferences,
                KeyChange(action="keep"),
                KeyChange(action="keep"),
            )
            next_record.preferences = memory.snapshot().preferences
            self.vault.write(next_record)
        return self.public()

    def migrate(self, revision, file_revision):
        with self.legacy.lock():
            record = self.record()
            raw, _, values = self.legacy.read()
            if record.revision != revision or digest(raw) != file_revision:
                raise SettingsError("Settings changed. Reload before migrating.")
            if self.legacy.snapshot().custom_runtime:
                raise SettingsError("Custom providers cannot be migrated by this workspace.")
            # Never overwrite a previously saved secure key with an older file value.
            record.groq = record.groq or KeyChange().replacement(values.get(GROQ_KEY))
            record.cloudflare = record.cloudflare or KeyChange().replacement(values.get(CLOUD_KEY))
            record.revision = str(uuid4())
            self.vault.write(record)
            # No backup: the verified vault remains the recovery authority if this write fails.
            self.legacy.replace(private_raw(raw, managed=True).decode())
        return self.public()

    def activate(self):
        with self.legacy.lock():
            raw, _, values = self.legacy.read()
            if values.get(GROQ_KEY) or values.get(CLOUD_KEY):
                raise SettingsError(
                    "Migrate existing provider keys before starting managed services."
                )
            self.legacy.replace(private_raw(raw, managed=True).decode())

    def nonsecret_environment(self, record):
        memory = self.runtime(record)
        return {
            k: v
            for k, v in memory.read()[2].items()
            if k.startswith("CONTEXTBRIDGE_") and k not in (GROQ_KEY, CLOUD_KEY)
        }

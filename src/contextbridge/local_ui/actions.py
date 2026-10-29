"""Explicit, bounded connection checks and operator-initiated local Compose apply."""

import json
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from contextbridge.formation.providers.chat import ChatClient
from contextbridge.formation.providers.config import GROQ_ENDPOINT
from contextbridge.formation.providers.interpretation import ChatSearchEvidenceJudge
from contextbridge.local_ui.settings import (
    CLOUD_KEY,
    GROQ_KEY,
    FileFormation,
    KeyChange,
    SettingsError,
    digest,
)
from contextbridge.retrieval.cloudflare import CloudflareEmbeddingBackend


def read_state(store, name):
    path = store.state / name
    if path.is_symlink() or store.state.is_symlink():
        raise SettingsError("Local settings state cannot be used safely.")
    if not path.exists():
        return {}
    try:
        with path.open("rb") as file:
            raw = file.read(8193)
        if len(raw) > 8192:
            raise ValueError
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (OSError, ValueError):
        raise SettingsError("Local settings state needs review before continuing.") from None


def write_state(store, name, value):
    from contextbridge.local_ui.settings import SettingsStore

    # Same atomic-private writer, with the operator-owned fixed metadata path.
    SettingsStore(store.state / name).replace(json.dumps(value) + "\n")


def check_provider(store, provider, revision, *, consent=False, transport=None):
    if provider not in ("groq", "cloudflare") or not consent:
        raise SettingsError("Confirm the single online test before continuing.")
    with store.lock():
        snapshot = store.snapshot()
        if snapshot.revision != revision or snapshot.custom_runtime:
            raise SettingsError("Settings changed or use a custom provider. Reload before testing.")
        _, _, values = store.read()
        prefs = snapshot.preferences
        key = KeyChange(
            action="replace", value=values.get(GROQ_KEY if provider == "groq" else CLOUD_KEY)
        ).replacement(None)
        if provider == "groq" and not prefs.groq_free_confirmed:
            raise SettingsError("Confirm your Groq Free plan and save settings before testing.")
        if provider == "cloudflare" and not prefs.cloudflare_account:
            raise SettingsError("Save the Cloudflare account ID before testing.")
        ledger = read_state(store, "provider-checks.json")
        today, now = datetime.now(UTC).date().isoformat(), time.time()
        try:
            if now - float(ledger.get("last_at", 0)) < 60:
                raise SettingsError("Wait one minute between connection checks.")
            counts = ledger.get("counts", {}) if ledger.get("day") == today else {}
            count = int(counts.get(provider, 0))
            if count >= 3:
                raise SettingsError("Three tests per provider per day are allowed. Try tomorrow.")
            if count < 0 or not isinstance(counts, dict):
                raise ValueError
        except (ValueError, TypeError, AttributeError):
            raise SettingsError("The connection-check allowance needs review.") from None
        counts[provider] = count + 1
        # Reserve before HTTP, including failures; no automatic retry or reset.
        write_state(store, "provider-checks.json", {"day": today, "last_at": now, "counts": counts})
    try:
        if provider == "groq":
            settings = FileFormation(
                provider="openai-compatible",
                base_url=GROQ_ENDPOINT,
                model=prefs.groq_model,
                verifier_model=prefs.groq_model,
                api_key=key,
                allow_hosted=True,
                allow_paid=False,
                groq_free_plan_confirmed=True,
                timeout_seconds=10,
                max_output_tokens=512,
            )
            verdict = ChatSearchEvidenceJudge(ChatClient(settings, transport=transport)).judge(
                "The example project uses SQLite.", "The example project uses SQLite."
            )
            if verdict != "supports":
                raise ValueError
        else:
            CloudflareEmbeddingBackend(
                api_key=key,
                base_url=f"https://api.cloudflare.com/client/v4/accounts/{prefs.cloudflare_account}/ai/v1",
                timeout_seconds=10,
                transport=transport,
            ).embed_batch(["The example project uses SQLite."])
    except Exception:
        return (
            False,
            "Connection check failed. Review the saved key, permissions and provider limits.",
        )
    return True, "Connection check passed. One synthetic request completed; no memories were sent."


def applied(store):
    try:
        return (
            read_state(store, "applied-settings.json").get("revision") == store.snapshot().revision
        )
    except (SettingsError, OSError):
        return False


def apply_services(store, revision, root, *, confirmed=False, runner=subprocess.run):
    root = Path(root).resolve()
    if not confirmed:
        raise SettingsError("Confirm the service restart before applying settings.")
    if store.path.parent.resolve() != root or not (root / "compose.yaml").is_file():
        raise SettingsError("Service restart is available only for this local installation.")
    with store.lock():
        raw, _, _ = store.read()
        if digest(raw) != revision:
            raise SettingsError("Settings changed. Reload before applying.")
        if store.snapshot().custom_runtime:
            raise SettingsError("Custom providers are managed outside this settings panel.")
        try:
            result = runner(
                [
                    "docker",
                    "compose",
                    "--file",
                    str(root / "compose.yaml"),
                    "--env-file",
                    str(store.path),
                    "--profile",
                    "workers",
                    "up",
                    "--build",
                    "--detach",
                ],
                cwd=root,
                env={k: v for k, v in os.environ.items() if not k.startswith("CONTEXTBRIDGE_")},
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=180,
                check=False,
            )
            if result.returncode != 0:
                raise ValueError
            if store.read()[0] != raw:
                raise SettingsError(
                    "Settings changed during restart. Review before applying again."
                )
            write_state(store, "applied-settings.json", {"revision": revision})
        except (OSError, ValueError, subprocess.TimeoutExpired):
            raise SettingsError(
                "The restart could not be confirmed. Check Docker before retrying; "
                "some services may have changed. Saved settings are preserved."
            ) from None
    return "Services updated. Refresh the workspace to check readiness."

"""Public-state test substitute; not a configuration backend or production fallback."""

from uuid import uuid4

from contextbridge.inspection.provider_settings import SettingsError, SettingsSnapshot


class FakeSettingsClient:
    def __init__(self):
        self.snapshot = SettingsSnapshot(revision=uuid4())
        self.changes = []
        self.staged = set()
        self.reads = 0

    def read(self):
        self.reads += 1
        return self.snapshot

    def apply(self, change):
        if change.expected_revision != self.snapshot.revision:
            raise SettingsError("conflict")
        updates = {"revision": uuid4(), "cloudflare_account_id": change.cloudflare_account_id}
        for provider in ("groq", "cloudflare"):
            action = getattr(change, f"{provider}_key_action")
            if action == "replace" and provider not in self.staged:
                raise SettingsError("replacement_missing")
            if action != "keep":
                updates[f"{provider}_key_configured"] = action == "replace"
        self.changes.append(change)
        self.snapshot = self.snapshot.model_copy(update=updates)
        self.staged.clear()
        return self.snapshot

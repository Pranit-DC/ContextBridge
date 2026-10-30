"""Native credential storage. No plaintext, null, chained or third-party fallback."""

import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass, field
from uuid import uuid4

from contextbridge.local_ui.settings import KeyChange, Preferences, SettingsError


@dataclass(repr=False)
class VaultRecord:
    revision: str = field(default_factory=lambda: str(uuid4()))
    preferences: Preferences = field(default_factory=Preferences)
    groq: str | None = None
    cloudflare: str | None = None

    def public(self):
        return {
            "revision": self.revision,
            "preferences": self.preferences.model_dump(),
            "groq_configured": bool(self.groq),
            "cloudflare_configured": bool(self.cloudflare),
        }

    def encoded(self):
        return json.dumps({**self.public(), "groq": self.groq, "cloudflare": self.cloudflare})

    @classmethod
    def decode(cls, raw):
        value = json.loads(raw)
        return cls(
            str(value["revision"]),
            Preferences.model_validate(value["preferences"]),
            KeyChange().replacement(value.get("groq")),
            KeyChange().replacement(value.get("cloudflare")),
        )


class NativeVault:
    def __init__(self, root, *, backend=None):
        self.service = (
            "ContextBridge:" + hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:24]
        )
        self._backend = backend

    def operation(self, action, value=None):
        if self._backend is not None:
            if action == "read":
                return self._backend.get_password(self.service, "providers")
            if action == "delete":
                return self._backend.delete_password(self.service, "providers")
            self._backend.set_password(self.service, "providers", value)
            return None
        # Native backends can open an OS unlock prompt. Bound it outside API threads;
        # a timed-out write may have committed, so callers must reload its revision.
        result = subprocess.run(
            [sys.executable, "-m", "contextbridge.product.vault", action, self.service],
            input=json.dumps({"value": value}).encode(),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
        if result.returncode or len(result.stdout) > 65_536:
            raise SettingsError("Unlock Windows Credential Manager or Linux Secret Service first.")
        return json.loads(result.stdout)["value"]

    def read(self):
        try:
            raw = self.operation("read")
            return VaultRecord.decode(raw) if raw else None
        except SettingsError:
            raise
        except Exception:
            raise SettingsError(
                "Secure storage is locked or unavailable. Unlock it and reload."
            ) from None

    def write(self, record):
        try:
            raw = record.encoded()
            self.operation("write", raw)
            if self.operation("read") != raw:
                raise ValueError
        except SettingsError:
            raise
        except Exception:
            raise SettingsError(
                "Secure settings could not be confirmed. Unlock storage and reload."
            ) from None


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["read", "write", "delete"])
    parser.add_argument("service")
    args = parser.parse_args()
    try:
        import keyring

        backend = keyring.get_keyring()
        allowed = {
            ("keyring.backends.Windows", "WinVaultKeyring"),
            ("keyring.backends.SecretService", "Keyring"),
        }
        if (type(backend).__module__, type(backend).__name__) not in allowed:
            return 2
        raw = sys.stdin.buffer.read(65_537)
        if len(raw) > 65_536:
            return 2
        value = json.loads(raw)["value"]
        if args.action == "read":
            value = backend.get_password(args.service, "providers")
        elif args.action == "write":
            backend.set_password(args.service, "providers", value)
            value = None
        else:
            backend.delete_password(args.service, "providers")
            value = None
        print(json.dumps({"value": value}))
        return 0
    except Exception:
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

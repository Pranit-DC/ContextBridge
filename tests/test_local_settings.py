import json
import os
from types import SimpleNamespace

import httpx
import pytest

from contextbridge.local_ui.actions import applied, apply_services, check_provider
from contextbridge.local_ui.settings import (
    CLOUD_KEY,
    GROQ_KEY,
    FileFormation,
    FileSettings,
    KeyChange,
    Preferences,
    SettingsError,
    SettingsStore,
)

TOKEN = "synthetic-local-access-token-1234567890"
GROQ = "synthetic-groq-private-key-123456"
CLOUD = "synthetic-cloudflare-private-key-123456"


@pytest.fixture
def store(tmp_path):
    path = tmp_path / ".env"
    path.write_text(
        "# Preserve installation settings.\n"
        f"CONTEXTBRIDGE_API_TOKEN='{TOKEN}'\n"
        "CONTEXTBRIDGE_DATABASE_URL='postgresql+psycopg://test:test@127.0.0.1/local_test'\n"
        "CONTEXTBRIDGE_CAPTURE_PROJECT_ID='contextbridge'\n"
        "CUSTOM_MULTILINE='first\nsecond'\n"
    )
    return SettingsStore(path)


def configured(store):
    return store.save(
        store.snapshot().revision,
        Preferences(
            processing=True,
            meaning_search=True,
            groq_free_confirmed=True,
            cloudflare_account="a" * 32,
        ),
        KeyChange(action="replace", value=GROQ),
        KeyChange(action="replace", value=CLOUD),
    )


@pytest.mark.parametrize("line_ending", [b"\n", b"\r\n"])
def test_save_round_trip_preserves_database_comments_and_multiline_and_hides_keys(
    store, monkeypatch, line_ending
):
    original = store.path.read_bytes().replace(b"\r\n", b"\n")
    store.path.write_bytes(original.replace(b"\n", line_ending))
    monkeypatch.setenv("CONTEXTBRIDGE_FORMATION_MODEL", "invalid-from-shell")
    snapshot = configured(store)
    assert snapshot.groq_key_configured and snapshot.cloudflare_key_configured
    assert GROQ not in repr(snapshot) and CLOUD not in repr(snapshot)
    raw, _, values = store.read()
    assert b"CUSTOM_MULTILINE='first\nsecond'".replace(b"\n", line_ending) in raw
    assert values["CUSTOM_MULTILINE"].replace("\r\n", "\n") == "first\nsecond"
    assert raw.startswith(b"# Preserve installation settings.")
    assert values[GROQ_KEY] == GROQ and values[CLOUD_KEY] == CLOUD
    service = FileSettings(
        **{
            name: values["CONTEXTBRIDGE_" + name.upper()]
            for name in FileSettings.model_fields
            if "CONTEXTBRIDGE_" + name.upper() in values
        }
    )
    assert service.formation_enabled and service.embedding_dimensions == 1024
    assert service.api_token.get_secret_value() == TOKEN
    formation = FileFormation(
        **{
            name: values["CONTEXTBRIDGE_FORMATION_" + name.upper()]
            for name in FileFormation.model_fields
            if "CONTEXTBRIDGE_FORMATION_" + name.upper() in values
        }
    )
    assert formation.is_groq_free()
    if os.name != "nt":
        assert store.path.stat().st_mode & 0o777 == 0o600


def test_removing_keys_disables_providers_without_secret_backups(store):
    snapshot = configured(store)
    updated = store.save(
        snapshot.revision,
        snapshot.preferences,
        KeyChange(action="remove"),
        KeyChange(action="remove"),
    )
    assert not updated.groq_key_configured and not updated.cloudflare_key_configured
    assert not updated.preferences.processing and not updated.preferences.meaning_search
    for path in store.path.parent.rglob("*"):
        if path.is_file():
            assert GROQ.encode() not in path.read_bytes()
            assert CLOUD.encode() not in path.read_bytes()
    assert not list(store.path.parent.glob(".settings-*"))


def test_stale_save_and_concurrent_lock_do_not_replace_settings(store):
    initial = store.snapshot()
    configured(store)
    saved = store.path.read_bytes()
    with pytest.raises(SettingsError, match="another window"):
        store.save(initial.revision, Preferences())
    assert store.path.read_bytes() == saved
    with store.lock(), pytest.raises(SettingsError, match="being changed"):
        with store.lock():
            pytest.fail("Concurrent editor entered the lock")


@pytest.mark.parametrize(
    "preferences,groq,cloud,message",
    [
        (Preferences(processing=True), None, None, "Groq key"),
        (Preferences(processing=True), KeyChange(action="replace", value=GROQ), None, "Free plan"),
        (
            Preferences(meaning_search=True),
            None,
            KeyChange(action="replace", value=CLOUD),
            "account ID",
        ),
        (
            Preferences(),
            KeyChange(action="replace", value="private\nINJECTED=value"),
            None,
            "valid provider key",
        ),
    ],
)
def test_invalid_configuration_never_partially_writes_or_echoes_keys(
    store, preferences, groq, cloud, message
):
    before = store.path.read_bytes()
    with pytest.raises(SettingsError, match=message) as error:
        store.save(store.snapshot().revision, preferences, groq, cloud)
    assert GROQ not in str(error.value) and CLOUD not in str(error.value)
    assert store.path.read_bytes() == before


def test_custom_provider_and_symlink_are_not_overwritten(store, tmp_path):
    with store.path.open("a") as file:
        file.write("CONTEXTBRIDGE_INTEGRATION_FACTORY='custom.module:make'\n")
    assert store.snapshot().custom_runtime
    with pytest.raises(SettingsError, match="Custom providers"):
        store.save(store.snapshot().revision, Preferences())
    if os.name != "nt":
        link = tmp_path / "alias.env"
        link.symlink_to(store.path)
        with pytest.raises(SettingsError):
            SettingsStore(link).read()


def test_atomic_write_failure_keeps_original_and_removes_temporary_file(store, monkeypatch):
    before = store.path.read_bytes()

    def fail(*args):
        raise OSError("synthetic private failure")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError):
        configured(store)
    assert store.path.read_bytes() == before
    assert not list(store.path.parent.glob(".settings-*"))


def test_referenced_credential_is_not_silently_requoted_or_resolved_from_shell(store, monkeypatch):
    with store.path.open("a") as file:
        file.write("CONTEXTBRIDGE_FORMATION_API_KEY=${EXTERNAL_PRIVATE_KEY}\n")
    monkeypatch.setenv("EXTERNAL_PRIVATE_KEY", GROQ)
    before = store.path.read_bytes()
    with pytest.raises(SettingsError, match="unsupported format") as error:
        store.save(store.snapshot().revision, Preferences())
    assert store.path.read_bytes() == before and GROQ not in str(error.value)


@pytest.mark.parametrize("provider", ["groq", "cloudflare"])
def test_explicit_checks_send_one_synthetic_request_with_no_memories_or_database_values(
    store, provider
):
    snapshot = configured(store)
    requests = []

    def handle(request):
        requests.append(request)
        assert TOKEN not in request.content.decode()
        assert "postgresql+psycopg" not in request.content.decode()
        if provider == "groq":
            body = json.loads(request.content)
            assert body["max_completion_tokens"] == 512 and not body["stream"]
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {"role": "assistant", "content": '{"judgment":"supports"}'},
                        }
                    ]
                },
            )
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0] + [0.0] * 1023}]})

    with pytest.raises(SettingsError, match="Confirm"):
        check_provider(store, provider, snapshot.revision)
    assert requests == []
    ok, message = check_provider(
        store, provider, snapshot.revision, consent=True, transport=httpx.MockTransport(handle)
    )
    assert ok and "passed" in message and len(requests) == 1
    with pytest.raises(SettingsError, match="one minute"):
        check_provider(
            store, provider, snapshot.revision, consent=True, transport=httpx.MockTransport(handle)
        )
    assert len(requests) == 1


def test_probe_failures_are_safe_and_consumed_allowance_cannot_retry_automatically(
    store, monkeypatch
):
    snapshot = configured(store)
    calls = []

    def unavailable(request):
        calls.append(request)
        return httpx.Response(401, text=GROQ + " private error")

    monkeypatch.setattr("contextbridge.local_ui.actions.time.time", lambda: 1000)
    ok, message = check_provider(
        store, "groq", snapshot.revision, consent=True, transport=httpx.MockTransport(unavailable)
    )
    assert not ok and GROQ not in message and len(calls) == 1
    for now in (1061, 1122):
        monkeypatch.setattr("contextbridge.local_ui.actions.time.time", lambda now=now: now)
        check_provider(
            store,
            "groq",
            snapshot.revision,
            consent=True,
            transport=httpx.MockTransport(unavailable),
        )
    monkeypatch.setattr("contextbridge.local_ui.actions.time.time", lambda: 1183)
    with pytest.raises(SettingsError, match="Three tests"):
        check_provider(
            store,
            "groq",
            snapshot.revision,
            consent=True,
            transport=httpx.MockTransport(unavailable),
        )
    assert len(calls) == 3
    assert GROQ not in (store.state / "provider-checks.json").read_text()


def test_apply_is_explicit_uses_fixed_compose_no_shell_or_keys_and_marks_only_success(
    store, monkeypatch
):
    snapshot = configured(store)
    (store.path.parent / "compose.yaml").write_text("services: {}\n")
    monkeypatch.setenv("CONTEXTBRIDGE_FORMATION_API_KEY", "stale-shell-key")
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        assert "--file" in command and "down" not in command and "--volumes" not in command
        assert GROQ not in repr(command) and CLOUD not in repr(command)
        assert not any(name.startswith("CONTEXTBRIDGE_") for name in kwargs["env"])
        return SimpleNamespace(returncode=0)

    with pytest.raises(SettingsError, match="Confirm"):
        apply_services(store, snapshot.revision, store.path.parent, runner=run)
    assert calls == [] and not applied(store)
    apply_services(store, snapshot.revision, store.path.parent, confirmed=True, runner=run)
    assert len(calls) == 1 and applied(store)
    updated = store.save(
        snapshot.revision, snapshot.preferences.model_copy(update={"grouping": True})
    )
    assert not applied(store)
    with pytest.raises(SettingsError, match="could not be confirmed"):
        apply_services(
            store,
            updated.revision,
            store.path.parent,
            confirmed=True,
            runner=lambda *a, **k: SimpleNamespace(returncode=1),
        )
    assert not applied(store)

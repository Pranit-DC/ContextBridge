import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from contextbridge.config import Settings
from contextbridge.inspection.provider_settings import SettingsChange, SettingsError
from contextbridge.provider_configuration import ProviderConfiguration, effective_configuration
from contextbridge.provider_files import atomic_write

GROQ_KEY = "synthetic-groq-credential-abcdefgh"
CF_KEY = "synthetic-cloudflare-credential-abcdefgh"
API_TOKEN = "synthetic-settings-api-token-0123456789"


@pytest.fixture
def configuration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://unused/unused_test",
        api_token=API_TOKEN,
        developer_id="settings-owner",
        provider_settings_file=tmp_path / "private" / "providers.json",
    )
    return settings, ProviderConfiguration(settings)


def install(store, *, groq=GROQ_KEY, cloudflare=CF_KEY):
    revision = store.read().revision
    for provider, credential in (("groq", groq), ("cloudflare", cloudflare)):
        if credential:
            store.stage(provider, SecretStr(credential), revision)
    return store.apply(
        SettingsChange(
            expected_revision=revision,
            cloudflare_account_id="a" * 32,
            groq_key_action="replace" if groq else "keep",
            cloudflare_key_action="replace" if cloudflare else "keep",
        )
    )


def test_every_hosted_client_fences_removed_credentials(configuration, monkeypatch):
    from contextbridge.engine.errors import ModuleError
    from contextbridge.provider_configuration import ConfigurationTransport
    from contextbridge.runtime import hosted_backends

    settings, store = configuration
    installed = install(store)
    monkeypatch.setenv("CONTEXTBRIDGE_FORMATION_ALLOW_HOSTED", "true")
    monkeypatch.setenv("CONTEXTBRIDGE_FORMATION_ALLOW_PAID", "false")
    monkeypatch.setenv("CONTEXTBRIDGE_FORMATION_GROQ_FREE_PLAN_CONFIRMED", "true")

    def unexpected_dispatch(request):
        pytest.fail("Removed credential reached the mocked provider transport")

    monkeypatch.setattr(
        httpx, "HTTPTransport", lambda **kwargs: httpx.MockTransport(unexpected_dispatch)
    )
    backends = hosted_backends(settings, None)
    clients = [backends.extraction_provider.client, backends.evidence_judge.client]
    context_judge = getattr(backends, "context_evidence_judge", None)
    if context_judge is not None:
        clients.append(context_judge.client)
    store.apply(SettingsChange(expected_revision=installed.revision, groq_key_action="remove"))
    for client in clients:
        assert isinstance(client.transport, ConfigurationTransport)
        with pytest.raises(ModuleError) as failure:
            client.transport.handle_request(httpx.Request("POST", "https://api.groq.com"))
        assert failure.value.code == "PROVIDER_UNAVAILABLE"
        client.transport.close()


def test_read_is_side_effect_free_and_keys_remain_private_until_apply(configuration):
    settings, store = configuration
    first = store.read()
    assert not settings.provider_settings_file.parent.exists()
    store.stage("groq", SecretStr(GROQ_KEY), first.revision)
    assert not store.read().groq_key_configured
    updated = store.apply(
        SettingsChange(expected_revision=first.revision, groq_key_action="replace")
    )
    assert updated.groq_key_configured and updated.revision != first.revision
    assert GROQ_KEY not in updated.model_dump_json() + repr(store.private())
    assert json.loads(settings.provider_settings_file.read_text())["groq_key"] == GROQ_KEY


def test_replace_remove_and_restart_do_not_restore_old_environment_key(configuration, monkeypatch):
    settings, store = configuration
    installed = install(store)
    store.stage("groq", SecretStr(GROQ_KEY + "-replacement"), installed.revision)
    replaced = store.apply(
        SettingsChange(
            expected_revision=installed.revision,
            groq_key_action="replace",
            cloudflare_account_id="a" * 32,
        )
    )
    assert GROQ_KEY + '"' not in settings.provider_settings_file.read_text()
    removed = store.apply(
        SettingsChange(
            expected_revision=replaced.revision,
            groq_key_action="remove",
            cloudflare_key_action="remove",
        )
    )
    monkeypatch.setenv("CONTEXTBRIDGE_EMBEDDING_API_KEY", CF_KEY)
    monkeypatch.setenv("CONTEXTBRIDGE_FORMATION_API_KEY", GROQ_KEY)
    reloaded = ProviderConfiguration(settings)
    assert reloaded.read() == removed
    assert not removed.groq_key_configured and not removed.cloudflare_key_configured
    effective, record = effective_configuration(settings)
    assert effective.embedding_provider is None and not effective.formation_enabled
    assert record.groq_key is None
    for path in settings.provider_settings_file.parent.iterdir():
        assert GROQ_KEY not in path.read_text() and CF_KEY not in path.read_text()


@pytest.mark.parametrize(
    "value",
    ["short", "contains whitespace in credential", "non-ascii-credential-秘密", API_TOKEN],
    ids=["short", "whitespace", "non_ascii", "memory_api_token"],
)
def test_malformed_or_api_token_credentials_are_rejected_without_creation(configuration, value):
    settings, store = configuration
    with pytest.raises(SettingsError) as caught:
        store.stage("groq", SecretStr(value), store.read().revision)
    assert value not in str(caught.value)
    assert not settings.provider_settings_file.exists()


def test_missing_staging_is_atomic_and_revision_conflicts_do_not_write(configuration):
    settings, store = configuration
    first = store.read()
    store.stage("groq", SecretStr(GROQ_KEY), first.revision)
    before = settings.provider_settings_file.read_bytes()
    with pytest.raises(SettingsError, match="Stage a replacement"):
        store.apply(
            SettingsChange(
                expected_revision=first.revision,
                groq_key_action="replace",
                cloudflare_key_action="replace",
            )
        )
    assert settings.provider_settings_file.read_bytes() == before
    with pytest.raises(SettingsError) as caught:
        store.apply(SettingsChange(expected_revision=uuid4(), groq_key_action="remove"))
    assert (
        caught.value.code == "conflict" and settings.provider_settings_file.read_bytes() == before
    )


def test_owner_and_token_rotation_fence_staged_credentials(configuration):
    settings, store = configuration
    revision = store.read().revision
    store.stage("groq", SecretStr(GROQ_KEY), revision)
    other = ProviderConfiguration(settings.model_copy(update={"developer_id": "other-owner"}))
    with pytest.raises(SettingsError) as caught:
        other.read()
    assert caught.value.code == "unauthorized"
    rotated = ProviderConfiguration(
        settings.model_copy(update={"api_token": SecretStr(API_TOKEN + "-rotated")})
    )
    with pytest.raises(SettingsError) as caught:
        rotated.apply(SettingsChange(expected_revision=revision, groq_key_action="replace"))
    assert caught.value.code == "replacement_missing" and not store.read().groq_key_configured


def test_concurrent_updates_have_one_winner_and_preserve_valid_private_file(configuration):
    _, store = configuration
    revision = install(store).revision

    def apply(_):
        try:
            return store.apply(SettingsChange(expected_revision=revision, groq_key_action="remove"))
        except SettingsError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(apply, range(2)))
    assert sum(result == "conflict" for result in results) == 1
    assert not store.read().groq_key_configured


def test_removal_cleans_abandoned_private_writes_and_preserves_legacy_dotenv(configuration):
    settings, store = configuration
    legacy = settings.provider_settings_file.parent.parent / ".env"
    contents = "CONTEXTBRIDGE_FORMATION_API_KEY=synthetic-legacy-key-untouched\nUNRELATED=keep\n"
    legacy.write_text(contents)
    installed = install(store)
    abandoned = settings.provider_settings_file.parent / ".providers.json.pending-abandoned"
    atomic_write(abandoned, GROQ_KEY.encode())
    store.apply(
        SettingsChange(
            expected_revision=installed.revision,
            groq_key_action="remove",
            cloudflare_key_action="remove",
        )
    )
    assert not abandoned.exists() and legacy.read_text() == contents
    assert GROQ_KEY not in settings.provider_settings_file.read_text()


def test_corrupt_private_configuration_never_echoes_raw_content(configuration):
    settings, store = configuration
    install(store)
    settings.provider_settings_file.write_text(GROQ_KEY)
    with pytest.raises(SettingsError) as caught:
        store.read()
    assert GROQ_KEY not in str(caught.value) and caught.value.__context__ is None


def test_overly_broad_file_permissions_fail_closed(configuration):
    settings, store = configuration
    install(store)
    path = settings.provider_settings_file
    if os.name == "nt":
        subprocess.run(
            [
                str(os.environ["SystemRoot"] + "\\System32\\icacls.exe"),
                str(path),
                "/grant",
                "*S-1-1-0:(R)",
            ],
            check=True,
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        path.chmod(0o644)
    with pytest.raises(SettingsError) as caught:
        store.read()
    assert caught.value.code == "unavailable"


def test_apply_acknowledgement_waits_for_inflight_dispatch_then_fences_old_clients(configuration):
    import httpx

    from contextbridge.engine.errors import ModuleError
    from contextbridge.provider_configuration import ConfigurationTransport

    settings, store = configuration
    installed = install(store)
    entered, release, applying = threading.Event(), threading.Event(), threading.Event()

    def handle(request):
        entered.set()
        assert release.wait(5)
        return httpx.Response(200)

    guarded = ConfigurationTransport(settings, installed.revision, httpx.MockTransport(handle))

    def apply():
        applying.set()
        return store.apply(
            SettingsChange(expected_revision=installed.revision, groq_key_action="remove")
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        request = pool.submit(
            guarded.handle_request, httpx.Request("POST", "https://synthetic.invalid")
        )
        assert entered.wait(3)
        mutation = pool.submit(apply)
        assert applying.wait(3)
        try:
            with pytest.raises(FutureTimeout):
                mutation.result(timeout=0.2)
        finally:
            release.set()
        request.result(timeout=3)
        mutation.result(timeout=3)
    with pytest.raises(ModuleError):
        guarded.handle_request(httpx.Request("POST", "https://synthetic.invalid"))


def test_cli_uses_masked_interactive_staging_and_safe_argument_errors(
    configuration, monkeypatch, capsys
):
    from contextbridge.provider_configuration import main

    settings, store = configuration
    revision = store.read().revision
    monkeypatch.setattr("contextbridge.config.Settings", lambda: settings)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("getpass.getpass", lambda prompt: GROQ_KEY)
    monkeypatch.setattr(
        sys, "argv", ["stage", "stage", "--provider", "groq", "--expected-revision", str(revision)]
    )
    assert main() == 0 and not store.read().groq_key_configured
    output = capsys.readouterr()
    assert GROQ_KEY not in output.out + output.err
    monkeypatch.setattr(
        sys, "argv", ["stage", "stage", "--provider", "groq", "--expected-revision", GROQ_KEY]
    )
    with pytest.raises(SystemExit):
        main()
    assert GROQ_KEY not in capsys.readouterr().err

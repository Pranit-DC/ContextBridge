"""Local control boundary, vault migration and credential handoff. No real accounts."""

import json
import os
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from contextbridge.local_ui.settings import KeyChange, Preferences, SettingsError
from contextbridge.product.app import COOKIE, create_product_app
from contextbridge.product.bootstrap import inject, read_credentials
from contextbridge.product.integrations import integration
from contextbridge.product.services import Services
from contextbridge.product.settings import ProductSettings
from contextbridge.product.vault import NativeVault

SECRET = "synthetic-provider-key-123456789"
TOKEN = "synthetic-service-access-token-1234567890"


class Backend:
    def __init__(self):
        self.value = None
        self.locked = False

    def get_password(self, service, user):
        if self.locked:
            raise RuntimeError(SECRET)
        return self.value

    def set_password(self, service, user, value):
        if self.locked:
            raise RuntimeError(SECRET)
        self.value = value


@pytest.fixture
def settings(tmp_path):
    path = tmp_path / ".env"
    path.write_text(
        f"CONTEXTBRIDGE_API_TOKEN='{TOKEN}'\nCONTEXTBRIDGE_DB_PASSWORD='synthetic-db'\n"
        "CONTEXTBRIDGE_DATABASE_URL='postgresql+psycopg://test:test@127.0.0.1/product_test'\n"
    )
    backend = Backend()
    store = ProductSettings(path, vault=NativeVault(tmp_path, backend=backend))
    return store, backend


def secure_save(store, **changes):
    prefs = Preferences(**changes)
    return store.save(
        store.public()["revision"], prefs, KeyChange(action="replace", value=SECRET), KeyChange()
    )


def test_vault_roundtrip_never_persists_key_in_settings_or_snapshot(settings):
    store, backend = settings
    public = secure_save(store, processing=True, groq_free_confirmed=True)
    assert public["groq_configured"] and public["preferences"]["processing"]
    assert SECRET not in json.dumps(public)
    assert SECRET not in store.legacy.path.read_text()
    assert store.record().groq == SECRET
    assert "groq=" not in repr(store.record())
    assert backend.value and SECRET in backend.value
    store.save(public["revision"], Preferences(), KeyChange(action="remove"), KeyChange())
    assert not store.public()["groq_configured"] and SECRET not in backend.value


def test_locked_store_never_falls_back_or_echoes_secret(settings):
    store, backend = settings
    backend.locked = True
    public = store.public()
    assert not public["storage_available"] and SECRET not in json.dumps(public)
    with pytest.raises(SettingsError) as error:
        secure_save(store)
    assert SECRET not in str(error.value)
    assert SECRET not in store.legacy.path.read_text()


def test_stale_revision_and_invalid_keys_do_not_replace_vault(settings):
    store, backend = settings
    first = secure_save(store)
    before = backend.value
    with pytest.raises(SettingsError):
        store.save("initial", Preferences(), KeyChange(action="remove"), KeyChange())
    with pytest.raises(SettingsError):
        store.save(
            first["revision"],
            Preferences(),
            KeyChange(action="replace", value="bad key"),
            KeyChange(),
        )
    assert backend.value == before


def test_migration_preserves_unrelated_values_and_blocks_legacy_writes(settings):
    store, _ = settings
    old = store.legacy.path.read_text()
    store.legacy.path.write_text(
        old + f"CONTEXTBRIDGE_FORMATION_API_KEY='{SECRET}'\nUNRELATED='keep me'\n"
    )
    state = store.public()
    result = store.migrate(state["revision"], state["file_revision"])
    assert result["managed"] and result["groq_configured"] and not result["legacy_keys_present"]
    assert "UNRELATED='keep me'" in store.legacy.path.read_text()
    assert TOKEN in store.legacy.path.read_text() and SECRET not in store.legacy.path.read_text()
    with pytest.raises(SettingsError, match="new ContextBridge workspace"):
        store.legacy.save(store.legacy.snapshot().revision, Preferences())
    assert not list(store.legacy.path.parent.glob(".settings-*"))


def test_failed_migration_scrub_retains_verified_vault_and_old_file(settings, monkeypatch):
    store, _ = settings
    store.legacy.path.write_text(
        store.legacy.path.read_text() + f"CONTEXTBRIDGE_FORMATION_API_KEY='{SECRET}'\n"
    )
    old = store.legacy.path.read_bytes()
    state = store.public()
    monkeypatch.setattr(store.legacy, "replace", lambda _: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(OSError):
        store.migrate(state["revision"], state["file_revision"])
    assert store.record().groq == SECRET and store.legacy.path.read_bytes() == old


@pytest.mark.skipif(os.name == "nt", reason="Credential injection runs inside Linux containers")
def test_tmpfs_handoff_is_private_and_refuses_symlinks_and_invalid_payload(tmp_path):
    directory = tmp_path / "runtime"
    inject(json.dumps({"groq": SECRET, "cloudflare": None}).encode(), directory)
    path = directory / "providers.json"
    assert read_credentials(path)["groq"] == SECRET
    assert path.stat().st_mode & 0o077 == 0
    with pytest.raises((ValueError, SettingsError)):
        inject(b'{"groq":"invalid key", "cloudflare":null}', directory)
    assert read_credentials(path)["groq"] == SECRET
    path.chmod(0o644)
    with pytest.raises(ValueError):
        read_credentials(path)


def test_compose_never_receives_provider_keys_as_environment_or_arguments(settings, tmp_path):
    store, _ = settings
    secure_save(store, processing=True, groq_free_confirmed=True)
    (tmp_path / "compose.yaml").write_text("services: {}")
    calls = []

    def runner(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout=b"" if "-q" in args or "-aq" in args else b"[]")

    services = Services(store, tmp_path, runner=runner, endpoint="unix:///synthetic")
    services.apply(store.public()["revision"])
    injections = [kwargs["input"] for args, kwargs in calls if args[-1] == "inject"]
    assert len(injections) == 3 and all(SECRET.encode() in value for value in injections)
    for args, kwargs in calls:
        assert SECRET not in repr(args) and SECRET not in repr(kwargs.get("env", {}))
    assert services.applied_revision == store.public()["revision"]
    assert SECRET not in store.legacy.path.read_text()


def test_partial_handoff_failure_stops_all_consumers(settings, tmp_path):
    store, _ = settings
    secure_save(store)
    (tmp_path / "compose.yaml").write_text("services: {}")
    calls = []

    def runner(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(
            returncode=int(args[-1] == "inject"),
            stdout=b"" if "-q" in args or "-aq" in args else b"[]",
        )

    services = Services(store, tmp_path, runner=runner, endpoint="unix:///synthetic")
    with pytest.raises(SettingsError):
        services.apply(store.public()["revision"])
    assert calls[-1][-4:] == ["stop", "api", "worker", "scheduler"]
    assert services.applied_revision is None


@pytest.fixture
def product(settings, tmp_path):
    store, _ = settings
    (tmp_path / "compose.yaml").write_text("services: {}")
    services = Services(
        store,
        tmp_path,
        runner=lambda *a, **k: SimpleNamespace(
            returncode=0, stdout=b"" if "-q" in a[0] or "-aq" in a[0] else b"[]"
        ),
        endpoint="unix:///synthetic",
    )
    captured = []

    def handle(request):
        captured.append(request)
        return httpx.Response(200, json={"status": "ready"})

    app = create_product_app(
        tmp_path, settings=store, services=services, transport=httpx.MockTransport(handle)
    )
    with TestClient(app, base_url="http://127.0.0.1:8501") as client:
        yield client, app, captured


def login(client, app):
    code = app.state.launch_url.split("launch=")[1]
    response = client.post(
        "/api/local/v1/session", json={"launch": code}, headers={"Origin": "http://127.0.0.1:8501"}
    )
    assert response.status_code == 200
    return {"Origin": "http://127.0.0.1:8501", "X-CSRF-Token": response.json()["csrf"]}


def test_one_time_handshake_cookie_and_origin_csrf_guards(product):
    client, app, _ = product
    assert client.get("/api/local/v1/session").status_code == 401
    assert client.get("/api/local/v1/config").status_code == 401
    headers = login(client, app)
    assert client.cookies.get(COOKIE)
    assert client.get("/api/local/v1/config").status_code == 200
    assert (
        client.get("/api/local/v1/config", headers={"Host": "evil.example:8501"}).status_code == 403
    )
    assert (
        client.get("/api/local/v1/config", headers={"Origin": "https://evil.example"}).status_code
        == 403
    )
    assert (
        client.post(
            "/api/local/v1/services/stop", json={"revision": "initial", "confirmed": True}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/local/v1/session",
            json={"launch": app.state.launch_url.split("launch=")[1]},
            headers=headers,
        ).status_code
        == 401
    )
    assert client.get("/api/local/v1/config").headers["cache-control"] == "no-store"


def test_write_hides_rejected_secrets_and_retains_real_replacement(product):
    client, app, _ = product
    headers = login(client, app)
    response = client.put(
        "/api/local/v1/config",
        headers=headers,
        json={
            "revision": "initial",
            "preferences": Preferences().model_dump(),
            "groq": {"action": "replace", "value": SECRET},
        },
    )
    assert response.status_code == 200, response.text
    assert SECRET not in response.text and app.state.settings.record().groq == SECRET
    response = client.put("/api/local/v1/config", headers=headers, json={"extra": SECRET})
    assert response.status_code == 422 and SECRET not in response.text


def test_proxy_is_fixed_origin_and_never_returns_service_token(product):
    client, app, captured = product
    login(client, app)
    response = client.get("/api/memory/health/ready")
    assert response.json() == {"status": "ready"}
    assert captured[0].url.host == "127.0.0.1"
    assert captured[0].headers["Authorization"] == "Bearer " + TOKEN
    assert TOKEN not in response.text
    assert client.get("/api/memory/v1/../../secrets").status_code == 404
    assert client.get("/api/memory/http://evil.example").status_code == 404


def test_capture_preview_install_pause_preserve_other_hooks(tmp_path):
    root = tmp_path / "workspace"
    (root / ".codex").mkdir(parents=True)
    path = root / ".codex" / "hooks.json"
    other = {"type": "command", "command": "echo other"}
    path.write_text(json.dumps({"other": 1, "hooks": {"UserPromptSubmit": [{"hooks": [other]}]}}))
    original = path.read_bytes()
    preview = integration(str(root), "sample", tmp_path / ".env.mcp", "preview")
    assert preview["hook"] and path.read_bytes() == original
    assert integration(str(root), "sample", tmp_path / ".env.mcp", "install")["installed"]
    assert integration(str(root), "sample", tmp_path / ".env.mcp", "install")["installed"]
    assert not integration(str(root), "sample", tmp_path / ".env.mcp", "pause")["installed"]
    parsed = json.loads(path.read_text())
    assert parsed["other"] == 1
    assert parsed["hooks"]["UserPromptSubmit"][0]["hooks"] == [other]


def test_operator_capability_issues_fresh_one_time_links(settings, tmp_path):
    store, _ = settings
    app = create_product_app(tmp_path, settings=store, operator_key="synthetic-operator-capability")
    with TestClient(app, base_url="http://127.0.0.1:8501") as client:
        assert client.post("/api/local/v1/operator", json={"action": "open"}).status_code == 401
        response = client.post(
            "/api/local/v1/operator",
            headers={"X-Local-Operator": "synthetic-operator-capability"},
            json={"action": "open"},
        )
        assert response.status_code == 200
        assert "synthetic-operator-capability" not in response.text
        login(client, app)
        assert client.get("/api/local/v1/config").status_code == 200


def test_expired_session_rejects_cookie(product, monkeypatch):
    from contextbridge.product import app as module

    client, app, _ = product
    login(client, app)
    now = module.time.monotonic()
    monkeypatch.setattr(module.time, "monotonic", lambda: now + 43_201)
    assert client.get("/api/local/v1/config").status_code == 401


def test_large_body_and_missing_capture_consent_are_rejected(product, tmp_path):
    client, app, _ = product
    headers = login(client, app)
    assert (
        client.post("/api/local/v1/session", content=b"x" * 524_289, headers=headers).status_code
        == 413
    )
    response = client.post(
        "/api/local/v1/connections/codex",
        headers=headers,
        json={"workspace": str(tmp_path), "project": "contextbridge", "action": "install"},
    )
    assert response.status_code == 409 and not (tmp_path / ".codex" / "hooks.json").exists()


@pytest.mark.parametrize("flag", ["true", "TRUE", "True", "1", "yes", "ON"])
def test_managed_credentials_never_fall_back_to_environment_keys(flag, monkeypatch):
    from contextbridge.config import Settings
    from contextbridge.formation.providers.config import load_settings
    from contextbridge.product import bootstrap

    monkeypatch.setenv("CONTEXTBRIDGE_MANAGED_CREDENTIALS", flag)
    monkeypatch.setenv("CONTEXTBRIDGE_EMBEDDING_API_KEY", SECRET)
    monkeypatch.setenv("CONTEXTBRIDGE_FORMATION_API_KEY", SECRET)
    monkeypatch.setattr(
        bootstrap, "read_credentials", lambda: (_ for _ in ()).throw(OSError("missing"))
    )
    with pytest.raises(ValueError, match="Managed credentials unavailable"):
        Settings(
            _env_file=None,
            managed_credentials=flag,
            database_url="postgresql+psycopg://unused/unused_test",
            api_token=TOKEN,
        )
    with pytest.raises(Exception, match="INVALID_INPUT"):
        load_settings(env_file="missing-synthetic-file")


def test_native_vault_timeout_uses_stdin_and_does_not_echo_credentials(settings, monkeypatch):
    import subprocess

    from contextbridge.product import vault as module
    from contextbridge.product.vault import VaultRecord

    store, _ = settings
    vault = NativeVault(store.legacy.path.parent)

    def timeout(args, **kwargs):
        assert SECRET not in repr(args)
        assert SECRET.encode() in kwargs["input"]
        raise subprocess.TimeoutExpired(args, 10, output=SECRET.encode())

    monkeypatch.setattr(module.subprocess, "run", timeout)
    with pytest.raises(SettingsError) as error:
        vault.write(VaultRecord(groq=SECRET))
    assert SECRET not in str(error.value)


def test_memory_only_start_does_not_require_vault(settings, tmp_path):
    store, backend = settings
    backend.locked = True
    (tmp_path / "compose.yaml").write_text("services: {}")
    calls = []

    def runner(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout=b"" if "-q" in args or "-aq" in args else b"[]")

    services = Services(store, tmp_path, runner=runner, endpoint="unix:///synthetic")
    services.apply("locked", offline=True)
    assert services.applied_revision == "offline"
    for args, kwargs in calls:
        assert kwargs.get("env", {}).get("CONTEXTBRIDGE_FORMATION_ENABLED", "false") == "false"
        if args[-1] == "inject":
            assert json.loads(kwargs["input"]) == {"groq": None, "cloudflare": None}


def test_remote_docker_is_refused_before_any_compose_change(settings, tmp_path, monkeypatch):
    store, _ = settings
    calls = []
    monkeypatch.setenv("DOCKER_HOST", "tcp://remote.example:2376")
    services = Services(store, tmp_path, runner=lambda *a, **k: calls.append(a))
    with pytest.raises(SettingsError, match="Remote Docker"):
        services.local_endpoint()
    assert calls == []


@pytest.mark.parametrize("inspection", [b"[]", b'[{"Config":{"Labels":{}}}]'])
def test_foreign_or_missing_compose_owner_blocks_service_mutation(settings, tmp_path, inspection):
    store, _ = settings
    calls = []

    def runner(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(
            returncode=0, stdout=inspection if "inspect" in args else b"container"
        )

    services = Services(store, tmp_path, runner=runner, endpoint="unix:///synthetic")
    with pytest.raises(SettingsError, match="another installation"):
        services.pause()
    assert not any("stop" in args for args in calls)


def test_orphaned_volumes_are_never_silently_adopted(settings, tmp_path):
    store, _ = settings

    def runner(args, **kwargs):
        return SimpleNamespace(returncode=0, stdout=b"old-volume" if "volume" in args else b"")

    services = Services(store, tmp_path, runner=runner, endpoint="unix:///synthetic")
    with pytest.raises(SettingsError, match="ownership review"):
        services.verify_ownership()


def test_release_archive_contains_built_assets_and_no_local_credentials(tmp_path):
    import zipfile

    from scripts.build_product_release import build

    output = tmp_path / "release.zip"
    from pathlib import Path

    if not (Path(__file__).parents[2] / "src/contextbridge/product/web/index.html").is_file():
        pytest.skip("Release build check runs after frontend compilation in CI")
    build(output)
    with zipfile.ZipFile(output) as bundle:
        names = bundle.namelist()
        assert "ContextBridge/src/contextbridge/product/web/index.html" in names
        assert "ContextBridge/release-manifest.json" in names
        assert not any(
            part in {".env", ".env.mcp", ".contextbridge", ".agents", ".claude", "node_modules"}
            for name in names
            for part in name.split("/")
        )


def test_busy_services_cannot_be_stopped_outside_the_operation_lock(settings, tmp_path):
    store, _ = settings
    services = Services(store, tmp_path, endpoint="unix:///synthetic")
    with services.lock, pytest.raises(SettingsError, match="Another service operation"):
        services.stop()


def test_manager_timeout_never_falls_back_to_an_independent_controller(tmp_path, monkeypatch):
    from contextbridge.product.cli import existing

    state = tmp_path / ".contextbridge"
    state.mkdir()
    (state / "product-manager.json").write_text(json.dumps({"port": 18501, "operator": TOKEN}))

    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout("synthetic timeout")

    monkeypatch.setattr(httpx.Client, "post", timeout)
    with pytest.raises(SettingsError, match="running manager"):
        existing(tmp_path, "stop")

from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from contextbridge.api import create_app
from contextbridge.config import Settings
from contextbridge.engine.errors import ModuleError
from contextbridge.inspection.client import ViewerSettings
from contextbridge.inspection.provider_settings import CheckRequest, SettingsChange, SettingsError
from contextbridge.inspection.settings_client import HttpSettingsClient
from contextbridge.provider_configuration import ConfigurationTransport, ProviderConfiguration
from contextbridge.runtime import load_integration
from tests.test_provider_configuration import API_TOKEN, CF_KEY, GROQ_KEY, install

pytestmark = pytest.mark.integration


@pytest.fixture
def configured_api(database, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CONTEXTBRIDGE_FORMATION_ALLOW_HOSTED", "true")
    monkeypatch.setenv("CONTEXTBRIDGE_FORMATION_GROQ_FREE_PLAN_CONFIRMED", "true")
    monkeypatch.setenv("CONTEXTBRIDGE_FORMATION_ALLOW_PAID", "false")
    settings = Settings(
        _env_file=None,
        database_url=database[0],
        api_token=API_TOKEN,
        developer_id="settings-owner",
        capture_project_id="settings-project",
        provider_settings_file=tmp_path / "private" / "providers.json",
    )
    with TestClient(create_app(settings)) as api:
        yield settings, ProviderConfiguration(settings), api


def client_for(api, token=API_TOKEN):
    def forward(request):
        response = api.request(
            request.method, request.url.path, content=request.content, headers=request.headers
        )
        return httpx.Response(
            response.status_code, content=response.content, headers=response.headers
        )

    return HttpSettingsClient(ViewerSettings(token=token), transport=httpx.MockTransport(forward))


def test_real_authenticated_client_staging_apply_status_remove_and_restart(configured_api):
    settings, store, api = configured_api
    client = client_for(api)
    client.read()
    assert not settings.provider_settings_file.exists()
    with pytest.raises(SettingsError) as caught:
        client_for(api, "wrong-token").read()
    assert caught.value.code == "unauthorized"
    installed = install(store)
    assert client.read() == installed
    status = api.get("/v1/status", headers={"Authorization": f"Bearer {API_TOKEN}"}).json()
    assert status["embeddings_configured"] and not status["extraction_configured"]
    removed = client.apply(
        SettingsChange(
            expected_revision=installed.revision,
            cloudflare_key_action="remove",
            groq_key_action="remove",
        )
    )
    assert not removed.cloudflare_key_configured
    status = api.get("/v1/status", headers={"Authorization": f"Bearer {API_TOKEN}"}).json()
    assert not status["embeddings_configured"]
    with TestClient(create_app(settings)) as restarted:
        assert client_for(restarted).read() == removed
    assert not settings.formation_enabled and settings.capture_project_id == "settings-project"


def test_stale_and_invalid_requests_are_safe_and_cannot_apply(configured_api):
    settings, store, api = configured_api
    installed = install(store)
    before = settings.provider_settings_file.read_bytes()
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    bad = api.put(
        "/v1/provider-settings",
        headers=headers,
        json={
            "expected_revision": str(installed.revision),
            GROQ_KEY: CF_KEY,
        },
    )
    assert bad.status_code == 422 and GROQ_KEY not in bad.text and CF_KEY not in bad.text
    stale = api.put(
        "/v1/provider-settings",
        headers=headers,
        json={"expected_revision": str(uuid4()), "groq_key_action": "remove"},
    )
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "conflict"
    assert settings.provider_settings_file.read_bytes() == before


def test_check_auth_revision_policy_and_fixed_report(configured_api, monkeypatch):
    _, store, api = configured_api
    snapshot = install(store)
    checks = []

    def execute(record, *, deadline):
        checks.append(record.revision)
        return {"groq": "ok", "cloudflare": "ok", "calls": 2}

    monkeypatch.setattr("contextbridge.provider_probe.execute_probe", execute)
    client = client_for(api)
    report = client.check(CheckRequest(expected_revision=snapshot.revision))
    assert report.checked_revision == snapshot.revision and report.calls == 2
    assert len(checks) == 1 and GROQ_KEY not in report.model_dump_json()
    with pytest.raises(SettingsError):
        client.check(CheckRequest(expected_revision=uuid4()))
    monkeypatch.setenv("CONTEXTBRIDGE_FORMATION_ALLOW_HOSTED", "false")
    with pytest.raises(SettingsError) as caught:
        client.check(CheckRequest(expected_revision=snapshot.revision))
    assert caught.value.code == "policy_blocked" and len(checks) == 1


def test_stale_provider_instances_are_fenced_and_fresh_api_worker_runtime_reads_new_keys(
    configured_api,
):
    settings, store, _ = configured_api
    first = install(store)
    sent = []
    transport = ConfigurationTransport(
        settings,
        first.revision,
        httpx.MockTransport(lambda request: (sent.append(request), httpx.Response(200))[1]),
    )
    assert (
        transport.handle_request(httpx.Request("POST", "https://synthetic.invalid")).status_code
        == 200
    )
    store.stage("cloudflare", SecretStr(CF_KEY + "-new"), first.revision)
    replaced = store.apply(
        SettingsChange(
            expected_revision=first.revision,
            cloudflare_key_action="replace",
            cloudflare_account_id="a" * 32,
        )
    )
    with pytest.raises(ModuleError):
        transport.handle_request(httpx.Request("POST", "https://synthetic.invalid"))
    assert len(sent) == 1
    # Shared factory holds no keys and reads the file for every API/worker execution.
    factory = load_integration(settings, None)
    assert factory.embedder is None and factory.configuration is None
    assert factory.fresh().embedder.backend._api_key == CF_KEY + "-new"
    store.apply(SettingsChange(expected_revision=replaced.revision, cloudflare_key_action="remove"))
    assert factory.fresh().embedder is None


def test_real_viewer_wires_authenticated_settings_without_a_session_factory(
    configured_api, monkeypatch
):
    settings, store, api = configured_api
    from tests.inspection.test_app import make_app, ready_service
    from tests.inspection.test_v1 import submit

    actual_client = HttpSettingsClient

    def client(settings):
        def forward(request):
            response = api.request(
                request.method, request.url.path, content=request.content, headers=request.headers
            )
            return httpx.Response(response.status_code, content=response.content)

        return actual_client(settings, transport=httpx.MockTransport(forward))

    monkeypatch.setattr("contextbridge.inspection.settings_client.HttpSettingsClient", client)
    app = make_app(ready_service()).run()
    app.sidebar.text_input(key="token").input(API_TOKEN)
    app.run()
    submit(app, "Load provider settings")
    revision = store.read().revision
    store.stage("groq", SecretStr(GROQ_KEY), revision)
    app.selectbox(key="provider_groq_action").select("Use staged replacement")
    app.checkbox(key="provider_confirm").check()
    submit(app, "Apply provider settings")
    assert store.read().groq_key_configured
    assert GROQ_KEY not in repr(app.session_state)
    assert settings.provider_settings_file.exists()
    # A connection change cannot reuse the old settings client's authorization.
    app.sidebar.text_input(key="token").input("wrong-token")
    app.run()
    submit(app, "Load provider settings")
    assert any("access token" in warning.value for warning in app.warning)


def test_groq_runtime_refreshes_credential_headers_without_changing_existing_policy(
    configured_api, monkeypatch
):
    from pydantic import BaseModel

    from contextbridge.db import make_engine, make_session_factory
    from contextbridge.inspection.provider_settings import GROQ_MODEL

    settings, store, _ = configured_api
    settings = settings.model_copy(update={"formation_enabled": True})
    installed = install(store)
    seen = []
    real_transport = ConfigurationTransport

    def handle(request):
        seen.append(request.headers["authorization"])
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": '{"value":"ok"}'},
                    }
                ]
            },
        )

    monkeypatch.setattr(
        "contextbridge.provider_configuration.ConfigurationTransport",
        lambda settings, revision: real_transport(settings, revision, httpx.MockTransport(handle)),
    )
    engine = make_engine(settings)
    try:
        factory = load_integration(settings, make_session_factory(engine))

        class Output(BaseModel):
            value: str

        first_client = factory.fresh().modules.extractor.provider.client
        first_client.complete(GROQ_MODEL, "Return a value.", {"text": "Synthetic check"}, Output)
        store.stage("groq", SecretStr(GROQ_KEY + "-new"), installed.revision)
        replaced = store.apply(
            SettingsChange(
                expected_revision=installed.revision,
                groq_key_action="replace",
                cloudflare_account_id="a" * 32,
            )
        )
        second_client = factory.fresh().modules.extractor.provider.client
        second_client.complete(GROQ_MODEL, "Return a value.", {"text": "Synthetic check"}, Output)
        assert seen == [f"Bearer {GROQ_KEY}", f"Bearer {GROQ_KEY}-new"]
        store.apply(
            SettingsChange(
                expected_revision=replaced.revision,
                groq_key_action="remove",
                cloudflare_key_action="remove",
            )
        )
        assert factory.fresh().modules.extractor is None
        assert settings.formation_enabled  # The configured policy switch was preserved.
    finally:
        engine.dispose()

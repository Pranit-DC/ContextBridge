from uuid import uuid4

import pytest
from pydantic import ValidationError

from contextbridge.inspection.provider_settings import (
    ProviderSelection,
    SettingsChange,
    SettingsController,
    SettingsError,
)
from tests.inspection.settings_fakes import FakeSettingsClient
from tests.inspection.test_app import make_app, ready_service
from tests.inspection.test_v1 import submit


def settings_app(client=None):
    app = make_app(ready_service())
    client = client or FakeSettingsClient()
    app.session_state["make_settings_client"] = lambda: client
    app.run()
    return app, client


def load_settings(app):
    submit(app, "Load provider settings")


def test_first_setup_is_available_before_memory_connection_and_never_mutates_on_load():
    app, client = settings_app()
    assert client.reads == 0 and not client.changes
    load_settings(app)
    assert client.reads == 1 and not client.changes
    assert any("missing" in t.value for t in app.text)
    assert len(app.selectbox(key="provider_groq_model").options) == 1
    assert len(app.selectbox(key="provider_cf_model").options) == 1


def test_signed_out_setup_requires_connection_and_creates_no_settings_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app = make_app(ready_service()).run()
    assert any("access token" in n.value for n in app.info)
    assert not list(tmp_path.iterdir())


def test_apply_requires_deliberate_confirmation_and_keeps_invalid_draft():
    app, client = settings_app()
    load_settings(app)
    app.text_input(key="provider_account").input("a" * 32)
    submit(app, "Apply provider settings")
    assert not client.changes
    app.checkbox(key="provider_confirm").check()
    app.text_input(key="provider_account").input("malformed")
    submit(app, "Apply provider settings")
    assert not client.changes and app.text_input(key="provider_account").value == "malformed"


def test_replace_and_remove_are_separate_explicit_actions():
    app, client = settings_app()
    load_settings(app)
    app.text_input(key="provider_account").input("a" * 32)
    app.checkbox(key="provider_confirm").check()
    app.selectbox(key="provider_groq_action").select("Use staged replacement")
    submit(app, "Apply provider settings")
    assert not client.changes
    client.staged.add("groq")
    submit(app, "Apply provider settings")
    assert len(client.changes) == 1 and client.snapshot.groq_key_configured
    app.selectbox(key="provider_groq_action").select("Remove key")
    submit(app, "Apply provider settings")
    assert len(client.changes) == 2 and not client.snapshot.groq_key_configured


def test_stale_settings_preserve_draft_without_retrying_or_overwriting():
    app, client = settings_app()
    load_settings(app)
    client.snapshot = client.snapshot.model_copy(update={"revision": uuid4()})
    app.text_input(key="provider_account").input("b" * 32)
    app.checkbox(key="provider_confirm").check()
    submit(app, "Apply provider settings")
    assert not client.changes
    assert app.text_input(key="provider_account").value == "b" * 32
    assert any("changed elsewhere" in n.value for n in app.warning)
    load_settings(app)
    submit(app, "Apply provider settings")
    assert len(client.changes) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"groq_provider": "other"},
        {"groq_model": "other"},
        {"cloudflare_model": "other"},
        {"cloudflare_account_id": "https://evil.invalid"},
    ],
)
def test_only_documented_provider_selection_is_accepted(changes):
    with pytest.raises(ValidationError):
        ProviderSelection(**changes)


def test_controller_refuses_unconfirmed_mutation():
    client = FakeSettingsClient()
    with pytest.raises(SettingsError):
        SettingsController(client).apply(
            SettingsChange(expected_revision=client.snapshot.revision), confirmed=False
        )
    assert not client.changes

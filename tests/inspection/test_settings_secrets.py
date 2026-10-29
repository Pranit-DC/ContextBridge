"""Credential leakage checks use only deliberately synthetic sentinels."""

import json
import traceback
from uuid import uuid4

import pytest

from contextbridge.inspection.provider_settings import (
    SettingsChange,
    SettingsController,
    SettingsError,
    SettingsSnapshot,
)
from tests.inspection.settings_fakes import FakeSettingsClient
from tests.inspection.test_settings import load_settings, settings_app
from tests.inspection.test_v1 import submit

SENTINEL = "synthetic-provider-key-do-not-display-123456"


@pytest.mark.parametrize(
    "response",
    [
        {"revision": uuid4(), "api_key": SENTINEL},
        SettingsSnapshot.model_construct(revision=uuid4(), groq_key_configured=SENTINEL),
        {"revision": uuid4(), "groq_model": SENTINEL},
    ],
)
def test_secret_bearing_or_malformed_response_cannot_cross_public_boundary(response, caplog):
    class Client:
        def read(self):
            return response

    with pytest.raises(SettingsError) as caught:
        SettingsController(Client()).read()
    rendered = "".join(traceback.format_exception(caught.value)) + caplog.text
    assert SENTINEL not in rendered
    assert caught.value.__context__ is None


def test_raw_transport_exception_and_chain_never_reach_viewer_or_logs(caplog):
    class BrokenClient:
        def read(self):
            raise RuntimeError(SENTINEL)

    app, _ = settings_app(BrokenClient())
    load_settings(app)
    shown = repr([(e.type, getattr(e, "value", None)) for e in app.main])
    shown += repr([(e.type, getattr(e, "value", None)) for e in app.sidebar])
    assert SENTINEL not in shown + caplog.text
    assert not app.exception


def test_service_side_synthetic_keys_never_enter_widget_messages_or_artifacts(tmp_path, caplog):
    # Isolated synthetic configuration represents owner-managed service state only.
    path = tmp_path / "synthetic-service.json"
    path.write_text(json.dumps({"groq_key": SENTINEL}), encoding="utf-8")
    client = FakeSettingsClient()
    client.staged.add("groq")
    app, _ = settings_app(client)
    load_settings(app)
    app.selectbox(key="provider_groq_action").select("Use staged replacement")
    app.checkbox(key="provider_confirm").check()
    submit(app, "Apply provider settings")
    messages = client.snapshot.model_dump_json() + repr(client.changes)
    state = repr(app.session_state)
    assert SENTINEL not in messages + state + caplog.text
    assert all("key" not in (e.key or "") for e in app.text_input)
    assert path.read_text(encoding="utf-8") == json.dumps({"groq_key": SENTINEL})
    assert list(tmp_path.iterdir()) == [path]


def test_invalid_action_instance_is_rejected_before_service_call():
    client = FakeSettingsClient()
    change = SettingsChange.model_construct(
        expected_revision=client.snapshot.revision, groq_key_action=SENTINEL
    )
    with pytest.raises(SettingsError) as caught:
        SettingsController(client).apply(change, confirmed=True)
    assert SENTINEL not in str(caught.value) and not client.changes

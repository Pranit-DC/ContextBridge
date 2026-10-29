import json
import traceback
from uuid import uuid4

import httpx
import pytest

from contextbridge.inspection.provider_settings import (
    SettingsChange,
    SettingsController,
    SettingsError,
    SettingsSnapshot,
    validate_settings,
)
from tests.inspection.settings_fakes import FakeSettingsClient
from tests.inspection.test_settings import load_settings, settings_app
from tests.inspection.test_settings_secrets import SENTINEL
from tests.inspection.test_v1 import submit


def configured():
    client = FakeSettingsClient()
    client.snapshot = SettingsSnapshot(
        revision=uuid4(),
        cloudflare_account_id="a" * 32,
        groq_key_configured=True,
        cloudflare_key_configured=True,
    )
    return client


def test_offline_validation_names_missing_settings_and_never_checks_online():
    app, client = settings_app()
    load_settings(app)
    submit(app, "Validate saved settings offline")
    warnings = " ".join(w.value for w in app.warning)
    assert "Groq key" in warnings and "Cloudflare key" in warnings and "account ID" in warnings
    assert client.checks == [] and client.changes == []


def test_online_check_discloses_data_and_bounds_before_explicit_consent_and_action():
    app, client = settings_app(configured())
    load_settings(app)
    captions = " ".join(c.value for c in app.caption)
    assert all(
        s in captions for s in ("Reply OK.", "quota", "charges", "10-second", "two requests")
    )
    submit(app, "Run bounded online check")
    assert not client.checks
    app.checkbox(key="provider_consent").check()
    app.run()
    assert not client.checks
    submit(app, "Run bounded online check")
    assert len(client.checks) == 1
    request = client.checks[0]
    assert (
        request.max_calls == 2
        and request.deadline_seconds == 10
        and request.max_output_tokens == 32
    )
    app.run()
    assert len(client.checks) == 1


def test_check_uses_saved_settings_and_removal_prevents_future_check():
    app, client = settings_app(configured())
    load_settings(app)
    app.text_input(key="provider_account").input("unsaved-invalid-account")
    app.checkbox(key="provider_consent").check()
    submit(app, "Run bounded online check")
    assert len(client.checks) == 1  # drafts never enter the check request
    app.text_input(key="provider_account").input("b" * 32)
    app.selectbox(key="provider_groq_action").select("Remove key")
    app.checkbox(key="provider_confirm").check()
    submit(app, "Apply provider settings")
    assert validate_settings(client.snapshot) == ["missing_groq_key"]
    submit(app, "Run bounded online check")
    assert len(client.checks) == 1


def test_replacement_becomes_complete_only_after_both_explicit_staged_actions():
    client = FakeSettingsClient()
    client.staged.update({"groq", "cloudflare"})
    change = SettingsChange(
        expected_revision=client.snapshot.revision,
        cloudflare_account_id="0" * 32,
        groq_key_action="replace",
        cloudflare_key_action="replace",
    )
    snapshot = SettingsController(client).apply(change, confirmed=True)
    assert validate_settings(snapshot) == []


@pytest.mark.parametrize("status", [401, 403, 429, 503])
def test_mocked_settings_transport_errors_are_safe_and_not_retried(status, caplog):
    client = configured()
    calls = []

    def handle(request):
        calls.append(json.loads(request.content))
        return httpx.Response(status, json={"detail": SENTINEL})

    def check(request):
        with httpx.Client(transport=httpx.MockTransport(handle), timeout=10) as http:
            response = http.post(
                "https://settings.invalid/test-only", json=request.model_dump(mode="json")
            )
            response.raise_for_status()

    client.check = check
    with pytest.raises(SettingsError) as caught:
        SettingsController(client).check(client.snapshot, consent=True)
    assert len(calls) == 1 and calls[0]["max_calls"] == 2
    assert caught.value.code == ("unauthorized" if status in (401, 403) else "unavailable")
    assert SENTINEL not in "".join(traceback.format_exception(caught.value)) + caplog.text


def test_timeout_preserves_drafts_and_recovers_on_a_new_explicit_check():
    client = configured()
    normal_check = client.check

    def timeout(request):
        raise httpx.ReadTimeout(SENTINEL)

    client.check = timeout
    app, _ = settings_app(client)
    load_settings(app)
    app.text_input(key="provider_account").input("b" * 32)
    app.checkbox(key="provider_consent").check()
    submit(app, "Run bounded online check")
    assert any("timed out" in w.value for w in app.warning)
    assert app.text_input(key="provider_account").value == "b" * 32
    client.check = normal_check
    submit(app, "Run bounded online check")
    assert len(client.checks) == 1 and not app.exception


@pytest.mark.parametrize(
    "outcome",
    ["authentication_failed", "timeout", "rate_limited", "unavailable", "invalid_response"],
)
def test_provider_failures_are_fixed_outcomes_and_stop_later_attempts(outcome):
    client = configured()
    client.check = lambda request: {
        "checked_revision": request.expected_revision,
        "groq": outcome,
        "cloudflare": "not_attempted",
        "calls": 1,
    }
    report = SettingsController(client).check(client.snapshot, consent=True)
    assert report.groq == outcome and report.cloudflare == "not_attempted" and report.calls == 1


@pytest.mark.parametrize(
    "updates",
    [
        {"calls": 3},
        {"api_key": SENTINEL},
        {"groq": SENTINEL},
        {"checked_revision": uuid4()},
        {"groq": "timeout", "cloudflare": "ok"},
    ],
)
def test_invalid_or_stale_check_reports_are_rejected(updates):
    client = configured()
    client.check = lambda request: {
        "checked_revision": request.expected_revision,
        "groq": "ok",
        "cloudflare": "ok",
        "calls": 2,
        **updates,
    }
    with pytest.raises(SettingsError):
        SettingsController(client).check(client.snapshot, consent=True)

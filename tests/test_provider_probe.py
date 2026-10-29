import json
import sys
import time

import httpx
import pytest
from pydantic import SecretStr

from contextbridge.inspection.provider_settings import SettingsError
from contextbridge.provider_configuration import PrivateConfiguration
from contextbridge.provider_probe import execute_probe, parse_events, run_probe
from tests.test_provider_configuration import CF_KEY, GROQ_KEY


def record():
    return PrivateConfiguration(
        owner="probe",
        cloudflare_account_id="a" * 32,
        groq_key=SecretStr(GROQ_KEY),
        cloudflare_key=SecretStr(CF_KEY),
    )


def successful(request):
    if request.url.host == "api.groq.com":
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})
    return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.1] * 1024}]})


def probe(handler):
    sent, events = [], []

    def handle(request):
        sent.append(request)
        return handler(request)

    run_probe(
        record(),
        lambda provider, status: events.append({"provider": provider, "status": status}),
        transport=httpx.MockTransport(handle),
    )
    return sent, events, parse_events(b"\n".join(json.dumps(e).encode() for e in events))


def test_fixed_payloads_only_two_requests_and_no_secret_progress(caplog):
    sent, events, result = probe(successful)
    assert len(sent) == 2 and result == {"groq": "ok", "cloudflare": "ok", "calls": 2}
    groq, cloudflare = [json.loads(r.content) for r in sent]
    assert groq["messages"] == [{"role": "user", "content": "Reply OK."}]
    assert groq["max_completion_tokens"] == 32
    assert cloudflare["input"] == ["ContextBridge connectivity check."]
    assert all(r.url.scheme == "https" for r in sent)
    assert GROQ_KEY not in json.dumps(events) + caplog.text
    assert CF_KEY not in json.dumps(events) + caplog.text


@pytest.mark.parametrize(
    "status,outcome",
    [
        (401, "authentication_failed"),
        (403, "authentication_failed"),
        (429, "rate_limited"),
        (500, "unavailable"),
        (302, "invalid_response"),
    ],
)
def test_first_failure_stops_without_retry_or_error_body_echo(status, outcome):
    sent, events, result = probe(lambda request: httpx.Response(status, text=GROQ_KEY))
    assert len(sent) == 1 and result == {"groq": outcome, "cloudflare": "not_attempted", "calls": 1}
    assert GROQ_KEY not in repr(events)


def test_cloudflare_failure_and_transport_timeout_count_attempts_honestly():
    def fail(request):
        if request.url.host == "api.groq.com":
            return successful(request)
        raise httpx.ReadTimeout(CF_KEY)

    sent, _, result = probe(fail)
    assert len(sent) == 2 and result == {"groq": "ok", "cloudflare": "timeout", "calls": 2}


@pytest.mark.parametrize(
    "body",
    [
        b"invalid json",
        b"x" * 2_097_153,
        json.dumps({"choices": [{"message": {"content": GROQ_KEY}}]}).encode(),
    ],
    ids=["malformed", "oversize", "credential_echo"],
)
def test_malformed_oversize_and_key_echo_responses_are_safe(body):
    sent, events, result = probe(lambda request: httpx.Response(200, content=body))
    assert len(sent) == 1 and result["groq"] == "invalid_response"
    assert GROQ_KEY not in repr(events)


def test_parent_hard_deadline_terminates_worker_and_uses_no_secret_argv_or_files(tmp_path):
    script = (
        "import json,sys,time; sys.stdin.buffer.read(); "
        "print(json.dumps({'provider':'groq','status':'started'}),flush=True); time.sleep(30)"
    )
    started = time.monotonic()
    result = execute_probe(record(), deadline=started + 1, command=[sys.executable, "-c", script])
    assert time.monotonic() - started < 4
    assert result == {"groq": "timeout", "cloudflare": "not_attempted", "calls": 1}
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "events",
    [
        [{"provider": "groq", "status": GROQ_KEY}],
        [{"provider": "cloudflare", "status": "started"}],
        [{"provider": "groq", "status": "started"}, {"provider": "groq", "status": "started"}],
        [{"provider": "groq", "status": "started", "secret": CF_KEY}],
    ],
)
def test_only_bounded_fixed_progress_events_can_escape_child(events):
    with pytest.raises(SettingsError) as caught:
        parse_events(b"\n".join(json.dumps(e).encode() for e in events))
    assert GROQ_KEY not in str(caught.value) and CF_KEY not in str(caught.value)

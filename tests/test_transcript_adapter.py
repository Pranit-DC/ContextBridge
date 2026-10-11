import json
from copy import deepcopy
from uuid import uuid4

import httpx
import pytest

from contextbridge.capture_adapters import cli
from contextbridge.capture_adapters.transcript import MAX_FILE_BYTES, TranscriptClient
from contextbridge.engine.errors import ModuleError
from tests.engine.fakes import fixture
from tests.test_mcp_adapter import TOKEN, settings


def event():
    result = fixture("captured-event")
    result["project_id"] = "project-a"
    return result


@pytest.mark.parametrize(
    "change",
    [
        {"project_id": "other-project"},
        {"capture_method": "verified_adapter"},
        {"scope": "developer", "project_id": None},
        {"messages": [{"message_id": "m1", "role": "user", "content": "sk-" + "z" * 40}]},
    ],
)
def test_invalid_or_unbound_transcript_never_reaches_http(change):
    calls = []
    client = TranscriptClient(settings(), transport=httpx.MockTransport(lambda r: calls.append(r)))
    with pytest.raises(ModuleError):
        client.submit({**event(), **change})
    assert calls == []


def test_lost_response_reuses_exact_event_and_never_retries():
    calls = []
    payload = event()
    original = deepcopy(payload)
    job_id = str(uuid4())

    def handle(request):
        calls.append(json.loads(request.content))
        if len(calls) == 1:
            raise httpx.ReadTimeout(TOKEN)
        return httpx.Response(
            202,
            json={
                "schema_version": 1,
                "event_id": payload["event_id"],
                "job_id": job_id,
                "status": "duplicate",
            },
        )

    client = TranscriptClient(settings(), transport=httpx.MockTransport(handle))
    with pytest.raises(ModuleError, match="PROVIDER_UNAVAILABLE") as error:
        client.submit(payload)
    assert error.value.retryable and len(calls) == 1
    assert str(client.submit(payload).job_id) == job_id
    assert calls[0] == calls[1] and payload == original


@pytest.mark.parametrize("status", [307, 401, 403, 404, 409, 422, 500])
def test_errors_never_follow_redirects_or_echo_response(status):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(
            status, json={"detail": TOKEN}, headers={"Location": "https://example.com"}
        )

    client = TranscriptClient(settings(), transport=httpx.MockTransport(handle))
    with pytest.raises(ModuleError) as error:
        client.submit(event())
    assert TOKEN not in str(error.value) and len(calls) == 1


def test_bounded_file_and_offline_cli_omit_private_text(tmp_path, monkeypatch, capsys):
    path = tmp_path / "event.json"
    path.write_bytes(b" " * (MAX_FILE_BYTES + 1))
    client = TranscriptClient(settings())
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        client.read(path)
    payload = event()
    path.write_text(json.dumps(payload))
    monkeypatch.setenv("CONTEXTBRIDGE_API_TOKEN", TOKEN)
    monkeypatch.setattr(
        "sys.argv", ["contextbridge-import", "--project-id", "project-a", "validate", str(path)]
    )
    assert cli.main() == 0
    output = capsys.readouterr()
    assert json.loads(output.out)["event_id"] == payload["event_id"]
    assert payload["messages"][0]["content"] not in output.out and TOKEN not in output.out
    path.write_text('{"private": "' + TOKEN + '"}')
    assert cli.main() == 1
    output = capsys.readouterr()
    assert TOKEN not in output.err and "INVALID_INPUT" in output.err
    path.write_text('{"event_id":"first","event_id":"second"}')
    with pytest.raises(ModuleError, match="INVALID_INPUT"):
        client.read(path)


def test_invalid_response_identity_is_rejected():
    client = TranscriptClient(
        settings(),
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                202,
                json={
                    "schema_version": 1,
                    "event_id": str(uuid4()),
                    "job_id": str(uuid4()),
                    "status": "accepted",
                },
            )
        ),
    )
    with pytest.raises(ModuleError, match="INVALID_PROVIDER_OUTPUT"):
        client.submit(event())

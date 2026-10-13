from types import SimpleNamespace

import pytest

from contextbridge.capture_adapters.codex_hook import submit_prompt
from contextbridge.capture_adapters.transcript import TranscriptClient
from contextbridge.engine.errors import ModuleError
from contextbridge.mcp_adapter.config import MCPSettings
from tests.conftest import TEST_TOKEN


class Receiver:
    def __init__(self):
        self.events = []

    def submit(self, event):
        self.events.append(event)
        return SimpleNamespace(job_id="synthetic-job")


def settings():
    return MCPSettings(
        _env_file=None, api_token=TEST_TOKEN, project_id="capture-test", agent_id="codex"
    )


def payload(root):
    return {
        "hook_event_name": "UserPromptSubmit",
        "cwd": str(root),
        "session_id": "session-1",
        "turn_id": "turn-1",
        "prompt": "I confirm that we need token access for API call",
    }


def test_hook_preserves_actual_user_prompt_and_stable_replay_without_content_copy(tmp_path):
    receiver = Receiver()
    event = payload(tmp_path)
    submit_prompt(event, settings(), tmp_path, client=receiver)
    submit_prompt(event, settings(), tmp_path, client=receiver)
    assert receiver.events[0] == receiver.events[1]
    assert receiver.events[0]["messages"][0]["content"] == event["prompt"]
    assert receiver.events[0]["messages"][0]["role"] == "user"
    assert receiver.events[0]["project_id"] == "capture-test"
    assert all(
        p.read_bytes() == b"" for p in (tmp_path / ".contextbridge/capture-receipts").iterdir()
    )
    event["turn_id"] = "turn-2"
    submit_prompt(event, settings(), tmp_path, client=receiver)
    assert receiver.events[-1]["event_id"] != receiver.events[0]["event_id"]


@pytest.mark.parametrize(
    "changes",
    [{"hook_event_name": "Stop"}, {"prompt": "x" * 8001}, {"session_id": ""}, {"cwd": "/"}],
)
def test_hook_rejects_other_events_oversize_and_foreign_workspace(tmp_path, changes):
    receiver = Receiver()
    with pytest.raises(ModuleError):
        submit_prompt({**payload(tmp_path), **changes}, settings(), tmp_path, client=receiver)
    assert receiver.events == []


def test_hook_secret_screening_precedes_network(tmp_path):
    event = {**payload(tmp_path), "prompt": "password=synthetic-secret"}
    with pytest.raises(ModuleError):
        submit_prompt(event, settings(), tmp_path, client=TranscriptClient(settings()))

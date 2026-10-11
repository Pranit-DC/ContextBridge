import pytest

from contextbridge.engine.errors import ModuleError
from contextbridge.formation import import_transcript


def import_event(event):
    return import_transcript(
        event["messages"],
        **{
            key: event[key]
            for key in (
                "event_id",
                "scope",
                "project_id",
                "agent",
                "session",
                "interaction",
                "occurred_at",
            )
        },
    )


def test_explicit_binding_and_replay_ids_survive(event):
    assert import_event(event) == event
    assert import_event(event) == import_event(event)


@pytest.mark.parametrize("change", ["scope", "session", "role", "unknown-field", "duplicate"])
def test_no_guessed_binding_or_message_shape(event, change):
    if change == "scope":
        event["project_id"] = None
    elif change == "session":
        event["session"] = ""
    elif change == "role":
        event["messages"][0]["role"] = "system"
    elif change == "unknown-field":
        event["messages"][0]["extra"] = "do not silently discard this"
    else:
        event["messages"] *= 2
    with pytest.raises(ModuleError, match="^INVALID_INPUT$"):
        import_event(event)


@pytest.mark.parametrize("count,length", [(21, 1), (1, 8001), (5, 7000)])
def test_transcript_limits_reject_without_truncation(event, count, length):
    event["messages"] = [
        {"message_id": str(index), "role": "tool", "content": "x" * length}
        for index in range(count)
    ]
    with pytest.raises(ModuleError, match="^INVALID_INPUT$"):
        import_event(event)

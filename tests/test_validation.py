from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from contextbridge.config import Settings
from contextbridge.schemas import CreateMemory, SearchMemories
from contextbridge.security import contains_secret


def payload(**changes):
    value = {
        "request_id": str(uuid4()),
        "scope": "project",
        "project_id": "contextbridge",
        "type": "DECISION",
        "content": "Use PostgreSQL.",
        "source": {
            "kind": "user",
            "agent": "codex",
            "session": "session-1",
            "interaction": "turn-1",
            "evidence": "We have decided to use PostgreSQL.",
        },
    }
    value.update(changes)
    return value


@pytest.mark.parametrize(
    "changes",
    [
        {"scope": "project", "project_id": None},
        {"scope": "developer", "project_id": "other"},
        {"content": "   "},
        {"valid_from": "2026-01-01T00:00:00"},
        {"valid_from": datetime.now(UTC) + timedelta(days=1)},
        {"developer_id": "another-owner"},
        {"conditions": {"environment": " "}},
    ],
)
def test_invalid_writes(changes):
    with pytest.raises(ValidationError):
        CreateMemory.model_validate(payload(**changes))


def test_agent_guess_is_not_an_allowed_source():
    value = payload()
    value["source"]["kind"] = "agent"
    with pytest.raises(ValidationError):
        CreateMemory.model_validate(value)


def test_valid_write_normalizes_whitespace_and_timezone():
    value = CreateMemory.model_validate(
        payload(content="  Use PostgreSQL.  ", valid_from="2026-01-01T05:30:00+05:30")
    )
    assert value.content == "Use PostgreSQL."
    assert value.valid_from == datetime(2026, 1, 1, tzinfo=UTC)


def test_search_requires_bounded_results():
    with pytest.raises(ValidationError):
        SearchMemories(scope="developer", query="database", limit=100)


def test_configuration_requires_long_token():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="postgresql://localhost/db", api_token="short")


@pytest.mark.parametrize(
    "value",
    [
        "api_key=abcdefgh",
        '{"password": "private-value"}',
        "sk-proj-abcdefghijklmnopqrstuvwxyz",
        "ghp_abcdefghijklmnopqrstuvwxyz012345",
        "-----BEGIN RSA PRIVATE KEY-----",
        "Bearer abcdefghijklmnopqrstuvwxyz",
        "postgresql://user:secret@localhost/db",
        "AKIAABCDEFGHIJKLMNOP",
    ],
)
def test_common_credentials_are_detected(value):
    assert contains_secret(value)


def test_ordinary_memory_is_not_rejected():
    assert not contains_secret("Use PostgreSQL and keep secrets in environment variables.")

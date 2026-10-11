"""Convert an explicitly bound message-list transcript; no host hooks or guessed scope."""

from datetime import datetime
from uuid import UUID

from contextbridge.formation.validation import screened_event


def import_transcript(
    messages: list[dict],
    *,
    event_id: str | UUID,
    scope: str,
    project_id: str | None,
    agent: str,
    session: str,
    interaction: str,
    occurred_at: str | datetime,
) -> dict:
    """Accept [{message_id, role, content}] and explicit caller-supplied binding.

    No truncation, automatic splitting, role inference or new IDs are performed.
    Reuse event/message IDs and identical payloads for retries.
    """
    event = {
        "schema_version": 1,
        "event_id": event_id,
        "scope": scope,
        "project_id": project_id,
        "agent": agent,
        "session": session,
        "interaction": interaction,
        "occurred_at": occurred_at,
        "capture_method": "manual_import",
        "messages": messages,
    }
    return screened_event(event).model_dump(mode="json")

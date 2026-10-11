"""Safe validation and provenance checks shared by formation entry points."""

from typing import Any

from pydantic import BaseModel, ValidationError

from contextbridge.contracts import Candidate, CapturedEvent
from contextbridge.engine.errors import ErrorCode, ModuleError
from contextbridge.security import contains_secret_fields


def validate[T: BaseModel](model: type[T], payload: Any, code: ErrorCode = "INVALID_INPUT") -> T:
    try:
        return model.model_validate(payload)
    except (ValidationError, TypeError, ValueError):
        raise ModuleError(code) from None


def screened_event(payload: dict) -> CapturedEvent:
    try:
        if contains_secret_fields(payload):
            raise ModuleError("INVALID_INPUT")
        event = validate(CapturedEvent, payload)
        # Shared models accept some Python collection forms; screen the canonical list too.
        if contains_secret_fields(event.model_dump(mode="json")):
            raise ModuleError("INVALID_INPUT")
    except RecursionError:
        raise ModuleError("INVALID_INPUT") from None
    return event


def has_provenance(candidate: Candidate, event: CapturedEvent) -> bool:
    """An exact excerpt proves its origin, not that it supports the proposed meaning."""
    if (
        candidate.event_id != event.event_id
        or candidate.scope != event.scope
        or candidate.project_id != event.project_id
        or candidate.source.agent != event.agent
        or candidate.source.session != event.session
        or candidate.source.interaction != event.interaction
    ):
        return False
    messages = {message.message_id: message for message in event.messages}
    referenced = [messages.get(ref.message_id) for ref in candidate.evidence_refs]
    if any(message is None or message.role == "assistant" for message in referenced):
        return False
    return any(
        message.role == candidate.source.kind and candidate.source.evidence in message.content
        for message in referenced
    )

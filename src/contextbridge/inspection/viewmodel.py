"""Display-ready, plain-text views of service data, in ordinary language.

Everything that came from the service or from a memory's content passes through ``plain`` so the
UI can show it as text: no HTML, no markdown, no control or direction-override characters.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from contextbridge.schemas import InspectionResponse, MemoryResponse, VersionResponse

LOW_CONFIDENCE = 0.7

TYPE_LABELS = {
    "FACT": "Fact",
    "DECISION": "Decision",
    "PREFERENCE": "Preference",
    "STATE": "Current state",
    "EVENT": "Event",
    "LESSON": "Lesson",
}
STATUS_LABELS = {"ACTIVE": "Current", "SUPERSEDED": "Replaced"}

# Direction overrides and invisible characters can disguise text, so they are never displayed.
_UNSAFE = re.compile("[​-‏‪-‮⁠-⁩﻿]")


def plain(value: object, limit: int | None = None) -> str:
    """Text safe to display literally: control and direction characters removed."""
    text = _UNSAFE.sub("", str(value))
    text = "".join(
        ch for ch in text if ch in "\n\t" or unicodedata.category(ch) not in ("Cc", "Cf", "Cs")
    )
    if limit is not None and len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def when(value: datetime | None) -> str:
    return value.strftime("%Y-%m-%d %H:%M UTC") if value else ""


def conditions_text(conditions: dict) -> str:
    if not conditions:
        return "Applies everywhere"
    return "Applies when " + ", ".join(
        f"{plain(k)} is {plain(v)}" for k, v in sorted(conditions.items())
    )


def validity_text(version: VersionResponse) -> str:
    if version.valid_to is None:
        return f"Since {when(version.valid_from)}"
    return f"{when(version.valid_from)} to {when(version.valid_to)}"


def source_text(version: VersionResponse) -> str:
    source = version.source
    who = "A user statement" if source.kind == "user" else "A tool result"
    return (
        f"{who}, recorded by {plain(source.agent)} "
        f"(session {plain(source.session)}, interaction {plain(source.interaction)})"
    )


def scope_label(memory: MemoryResponse) -> str:
    if memory.scope == "developer":
        return "All your projects"
    return f"Project {plain(memory.project_id)}"


def uncertainty(decision_state: str, confidence: float | None) -> str | None:
    if decision_state == "contested":
        return "Disputed: the saved sources disagree. Check the evidence before relying on this."
    if confidence is not None and confidence < LOW_CONFIDENCE:
        return "Lower confidence: this was inferred and is less certain."
    return None


@dataclass(frozen=True)
class MemoryRow:
    memory_id: str
    text: str
    type_label: str
    scope_label: str
    status_label: str
    conditions: str
    validity: str
    source: str
    version_number: int
    uncertainty: str | None = None


def row_from(memory: dict, decision_state: str = "clear", confidence: float | None = None):
    mem = MemoryResponse.model_validate(memory)
    version = mem.version
    return MemoryRow(
        memory_id=str(mem.id),
        text=plain(version.content, 400),
        type_label=TYPE_LABELS.get(mem.type, plain(mem.type)),
        scope_label=scope_label(mem),
        status_label=STATUS_LABELS.get(version.status, plain(version.status)),
        conditions=conditions_text(mem.conditions),
        validity=validity_text(version),
        source=source_text(version),
        version_number=version.number,
        uncertainty=uncertainty(decision_state, confidence),
    )


def rows_from_memories(memories: list[dict]) -> list[MemoryRow]:
    return [row_from(memory) for memory in memories]


def rows_from_browse(items: list[dict]) -> list[MemoryRow]:
    return [
        row_from(item["memory"], item.get("decision_state", "clear"), item.get("confidence"))
        for item in items
    ]


@dataclass(frozen=True)
class VersionView:
    number: int
    status_label: str
    content: str
    validity: str
    recorded: str
    source: str
    evidence: str
    is_current: bool


@dataclass(frozen=True)
class DetailView:
    memory_id: str
    type_label: str
    scope_label: str
    conditions: str
    current: VersionView
    history: list[VersionView]  # newest first
    relationships: list[str] = field(default_factory=list)
    # The version a correction must be based on; the service rejects a stale one.
    expected_version: int = 1


def _version_view(version: VersionResponse, current_number: int) -> VersionView:
    return VersionView(
        number=version.number,
        status_label=STATUS_LABELS.get(version.status, plain(version.status)),
        content=plain(version.content),
        validity=validity_text(version),
        recorded=f"Recorded {when(version.recorded_at)}",
        source=source_text(version),
        evidence=plain(version.source.evidence),
        is_current=version.number == current_number,
    )


def detail_from(inspection: dict) -> DetailView:
    result = InspectionResponse.model_validate(inspection)
    memory = result.memory
    numbers = {version.id: version.number for version in (result.history or [memory.version])}
    history = result.history or [memory.version]
    views = [_version_view(v, memory.current_version) for v in history]
    views.sort(key=lambda view: view.number, reverse=True)
    relationships = []
    for edge in result.edges:
        newer, older = numbers.get(edge.from_version_id), numbers.get(edge.to_version_id)
        if newer is None or older is None:
            continue
        if edge.relation == "supersedes":
            relationships.append(f"Version {newer} replaced version {older}.")
        else:
            relationships.append(
                f"Version {newer} is linked to version {older} ({plain(edge.relation)})."
            )
    current = next((v for v in views if v.is_current), views[0])
    return DetailView(
        memory_id=str(memory.id),
        type_label=TYPE_LABELS.get(memory.type, plain(memory.type)),
        scope_label=scope_label(memory),
        conditions=conditions_text(memory.conditions),
        current=current,
        history=views,
        relationships=sorted(relationships),
        expected_version=memory.current_version,
    )


@dataclass(frozen=True)
class Notice:
    level: Literal["info", "success", "warning", "error"]
    text: str

"""Scope-bound provenance and explicit uncertain-interval context; no model calls."""

from datetime import UTC

from sqlalchemy import select

from contextbridge.engine.errors import EngineError
from contextbridge.evidence_time.contracts import TemporalBounds
from contextbridge.models import Memory, MemoryVersion, VersionProvenance
from contextbridge.persistence.locks import lock_owner
from contextbridge.security import contains_secret_fields
from contextbridge.service import memory_response


def scoped_memory(session, settings, payload):
    if contains_secret_fields(payload.model_dump(mode="json")):
        raise EngineError("INVALID_INPUT", 422)
    memory = session.scalar(
        select(Memory)
        .where(
            Memory.id == payload.memory_id,
            Memory.developer_id == settings.developer_id,
            Memory.scope == payload.scope,
            Memory.project_id == payload.project_id,
        )
        .execution_options(populate_existing=True)
    )
    if memory is None:
        raise EngineError("OUT_OF_SCOPE", 404)
    return memory


def provenance(session, settings, payload):
    lock_owner(session, settings.developer_id)
    memory = scoped_memory(session, settings, payload)
    version = session.scalar(
        select(MemoryVersion).where(
            MemoryVersion.memory_id == memory.id,
            MemoryVersion.number == (payload.version or memory.current_version),
        )
    )
    if version is None:
        raise EngineError("OUT_OF_SCOPE", 404)
    value = session.get(VersionProvenance, version.id)
    result = {
        "memory_id": str(memory.id),
        "version": version.number,
        "metadata": (
            {
                **value.metadata_json,
                "previous_version_id": str(value.previous_version_id)
                if value.previous_version_id
                else None,
            }
            if value
            else {"schema_version": 1, "precision": "instant"}
        ),
    }
    session.commit()
    return result


def temporal_context(session, settings, payload):
    lock_owner(session, settings.developer_id)
    memory = scoped_memory(session, settings, payload)
    if memory.current_version != payload.expected_version:
        raise EngineError("VERSION_CONFLICT", 409)
    if any(payload.conditions.get(k) != v for k, v in memory.conditions.items()):
        raise EngineError("OUT_OF_SCOPE", 404)
    rows = session.execute(
        select(MemoryVersion, VersionProvenance)
        .outerjoin(VersionProvenance, VersionProvenance.version_id == MemoryVersion.id)
        .where(MemoryVersion.memory_id == memory.id)
        .order_by(MemoryVersion.number.desc())
        .limit(201)
    ).all()
    if len(rows) > 200:
        raise EngineError("INVALID_INPUT", 422)
    items, warnings = [], []
    for version, extension in rows:
        if extension is None:
            continue
        temporal = TemporalBounds.model_validate(extension.metadata_json["temporal"])
        if (
            temporal.relation != "context_only"
            and temporal.earliest <= payload.as_of < temporal.guaranteed_from
            and (version.valid_to is None or payload.as_of < version.valid_to)
        ):
            items.append(
                {
                    "memory": memory_response(memory, version).model_dump(mode="json"),
                    "decision_state": version.decision_state,
                    "role": "possible_after",
                    "applicability": "uncertain_transition",
                    "temporal": temporal.model_dump(mode="json"),
                }
            )
            if extension.previous_version_id:
                previous = session.execute(
                    select(Memory, MemoryVersion)
                    .join(MemoryVersion, MemoryVersion.memory_id == Memory.id)
                    .where(
                        MemoryVersion.id == extension.previous_version_id,
                        Memory.developer_id == settings.developer_id,
                        Memory.scope == payload.scope,
                        Memory.project_id == payload.project_id,
                    )
                ).first()
                if previous is not None and all(
                    payload.conditions.get(k) == v for k, v in previous[0].conditions.items()
                ):
                    items.insert(
                        0,
                        {
                            "memory": memory_response(*previous).model_dump(mode="json"),
                            "decision_state": previous[1].decision_state,
                            "role": "possible_before",
                            "applicability": "uncertain_transition",
                            "temporal": temporal.model_dump(mode="json"),
                        },
                    )
            warnings.append("TRANSITION_TIME_UNCERTAIN")
            break
    if not items:
        for version, extension in rows:
            if version.valid_from <= payload.as_of and (
                version.valid_to is None or payload.as_of < version.valid_to
            ):
                items.append(
                    {
                        "memory": memory_response(memory, version).model_dump(mode="json"),
                        "decision_state": version.decision_state,
                        "role": "applicable_at_time",
                        "applicability": "contested"
                        if version.decision_state == "contested"
                        else "applicable",
                        "temporal": extension.metadata_json["temporal"] if extension else None,
                    }
                )
                break
    if any(i["decision_state"] == "contested" for i in items):
        warnings.append("CONTESTED_MEMORY")
    if len(items) > payload.limit:
        warnings.append("TEMPORAL_ALTERNATIVES_OMITTED")
    result = {
        "schema_version": 2,
        "as_of": payload.as_of.astimezone(UTC).isoformat(),
        "items": items[: payload.limit],
        "warnings": warnings or ([] if items else ["NO_APPLICABLE_MEMORY"]),
    }
    session.commit()
    return result

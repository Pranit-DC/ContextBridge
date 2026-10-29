from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest

from contextbridge.contracts import Candidate, CapturedEvent
from contextbridge.engine.grouping import aggregate, distribute
from tests.engine.fakes import fixture


def distributed_candidate(evidence):
    first = fixture("captured-event")
    first.update(event_id=str(uuid4()), occurred_at="2026-10-10T10:00:00Z")
    second = deepcopy(first)
    second.update(
        event_id=str(uuid4()), occurred_at="2026-10-12T12:00:00Z", interaction="later-import"
    )
    second["messages"] = [{"message_id": "original-message", "role": "user", "content": evidence}]
    rows = [
        (SimpleNamespace(id=uuid4()), SimpleNamespace(payload=event)) for event in (first, second)
    ]
    combined, mapping = aggregate(rows)
    raw = fixture("candidate")
    raw.update(event_id=str(combined.event_id), valid_from=combined.occurred_at.isoformat())
    raw["source"].update(
        agent=combined.agent,
        session=combined.session,
        interaction=combined.interaction,
        evidence=evidence,
    )
    raw["evidence_refs"] = [{"event_id": str(combined.event_id), "message_id": "g1m0"}]
    candidates, deferred = distribute([Candidate.model_validate(raw)], mapping, rows)
    assert not deferred
    candidate = candidates[rows[1][0].id][0]
    assert candidate.event_id == CapturedEvent.model_validate(second).event_id
    assert candidate.source.interaction == "later-import"
    assert candidate.evidence_refs[0].message_id == "original-message"
    assert candidate.source.evidence == evidence
    return candidate


@pytest.mark.parametrize("literal", ["2026-10-10T10:00:00Z", "2026-10-10T15:30:00+05:30"])
def test_explicit_effective_time_matching_group_anchor_is_not_replaced_by_later_import_time(
    literal,
):
    candidate = distributed_candidate(f"We switched to SQLite at {literal}.")
    assert candidate.valid_from.isoformat() == "2026-10-10T10:00:00+00:00"


def test_default_group_time_rebinds_to_original_event_time_without_changing_evidence():
    candidate = distributed_candidate("Use SQLite, db_v1.sqlite, with a 64 MB limit.")
    assert candidate.valid_from.isoformat() == "2026-10-12T12:00:00+00:00"

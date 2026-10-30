from datetime import UTC, datetime
from uuid import uuid4

import pytest

from contextbridge.evidence_time.temporal import TemporalAmbiguity, bounds, one_fragment


def trace(at="2026-10-10T10:00:00+05:30", zone="Asia/Kolkata"):
    return {"occurred_at": at, "source_timezone": zone, "event_id": str(uuid4())}


@pytest.mark.parametrize(
    "quote,precision,start,end",
    [
        ("Switched yesterday.", "day", "2026-10-08T18:30:00+00:00", "2026-10-09T18:30:00+00:00"),
        ("Switched last week.", "week", "2026-09-27T18:30:00+00:00", "2026-10-04T18:30:00+00:00"),
        (
            "Switched between 2026-10-01 and 2026-10-03.",
            "range",
            "2026-09-30T18:30:00+00:00",
            "2026-10-03T18:30:00+00:00",
        ),
        (
            "Switched 2026-10-01T13:45:00Z.",
            "instant",
            "2026-10-01T13:45:00+00:00",
            "2026-10-01T13:45:00+00:00",
        ),
    ],
)
def test_preserves_calendar_precision(quote, precision, start, end):
    result = one_fragment(quote, trace(), "state_transition")
    assert result.precision == precision
    assert result.earliest.isoformat() == start
    assert result.latest.isoformat() == end


@pytest.mark.parametrize("day,expected", [("2026-03-08", 23), ("2026-11-01", 25)])
def test_calendar_days_follow_dst(day, expected):
    result = one_fragment(
        f"Switched on {day}.", trace("2026-12-01T10:00:00Z", "America/New_York"), "state_transition"
    )
    assert (result.latest - result.earliest).total_seconds() == expected * 3600


@pytest.mark.parametrize(
    "quote,at,zone",
    [
        ("Switched yesterday at 01:30.", "2026-11-02T10:00:00Z", "America/New_York"),
        ("Switched yesterday at 02:30.", "2026-03-09T10:00:00Z", "America/New_York"),
        ("Switched tomorrow.", "2026-10-10T10:00:00Z", "UTC"),
        ("Switched around yesterday.", "2026-10-10T10:00:00Z", "UTC"),
        ("Switched on 2026-10-11.", "2026-10-10T10:00:00Z", "UTC"),
        ("Switched yesterday and last week.", "2026-10-10T10:00:00Z", "UTC"),
        ("Switched yesterday or 2026-10-01.", "2026-10-10T10:00:00Z", "UTC"),
        ("Switched 2026-10-01T13:45:00.", "2026-10-10T10:00:00Z", "UTC"),
        ("Switched on 2026-10-01 at 13:45.", "2026-10-10T10:00:00Z", "UTC"),
    ],
)
def test_ambiguous_or_future_effective_time_defers(quote, at, zone):
    with pytest.raises(TemporalAmbiguity):
        one_fragment(quote, trace(at, zone), "state_transition")


def test_future_deadline_is_context_not_a_future_state_change():
    result = one_fragment("Use SQLite until 2026-12-01.", trace(), "context_only")
    assert result.earliest > result.guaranteed_from
    assert result.guaranteed_from == datetime(2026, 10, 10, 4, 30, tzinfo=UTC)


def test_cross_turn_claim_cannot_apply_before_its_latest_support():
    fragments = [
        {"message_id": "one", "quote": "Use SQLite."},
        {"message_id": "two", "quote": "Confirmed."},
    ]
    mapping = {"one": trace("2026-10-09T10:00:00Z"), "two": trace("2026-10-10T10:00:00Z")}
    result = bounds(fragments, mapping, "state_transition")
    assert result.guaranteed_from == datetime(2026, 10, 10, 10, tzinfo=UTC)


def test_each_relative_phrase_uses_its_own_source_time():
    fragments = [
        {"message_id": "one", "quote": "Switched yesterday."},
        {"message_id": "two", "quote": "Switched 2 days ago."},
    ]
    mapping = {
        "one": trace("2026-10-10T10:00:00Z", "UTC"),
        "two": trace("2026-10-11T10:00:00Z", "UTC"),
    }
    result = bounds(fragments, mapping, "state_transition")
    assert result.earliest == datetime(2026, 10, 9, tzinfo=UTC)
    mapping["two"] = trace("2026-10-12T10:00:00Z", "UTC")
    with pytest.raises(TemporalAmbiguity):
        bounds(fragments, mapping, "state_transition")

from datetime import datetime

import pytest

from contextbridge.engine.relative_time import normalize_relative


def source(value="2026-10-15T00:15:00+05:30"):
    return datetime.fromisoformat(value)


def test_sqlite_yesterday_is_a_date_without_an_invented_time():
    result = normalize_relative(
        "We switched to SQLite yesterday.", source(), timezone="Asia/Kolkata"
    )
    assert result.text == "We switched to SQLite 2026-10-14."
    assert str(result.start_date) == "2026-10-14"
    assert result.precision == "date" and result.instant is None


@pytest.mark.parametrize(
    "zone,expected",
    [
        ("Asia/Kolkata", "2026-10-14"),
        ("America/Los_Angeles", "2026-10-13"),
    ],
)
def test_delayed_import_and_day_boundary_use_source_not_receipt(zone, expected):
    result = normalize_relative("Switched yesterday", source(), timezone=zone)
    assert str(result.start_date) == expected


def test_last_week_is_previous_calendar_week_with_date_precision():
    result = normalize_relative("Switched last week", source(), timezone="Asia/Kolkata")
    assert (str(result.start_date), str(result.end_date)) == ("2026-10-05", "2026-10-12")
    assert result.precision == "date_range" and result.instant is None


@pytest.mark.parametrize(
    "text",
    [
        "Maybe we switched yesterday",
        "Switched around yesterday",
        "Switched last Friday",
        "Switched recently",
        "Switched yesterday and today",
        "Switch tomorrow",
        "Switched yesterday at 25:00",
        "Switched 999999 days ago",
    ],
)
def test_uncertain_or_ambiguous_dates_defer(text):
    assert normalize_relative(text, source(), timezone="UTC").precision == "deferred"


@pytest.mark.parametrize(
    "timestamp,zone",
    [(None, "UTC"), (source(), None), (datetime(2026, 10, 15), "UTC"), (source(), "invalid/zone")],
)
def test_missing_reference_context_defers(timestamp, zone):
    assert (
        normalize_relative("Switched yesterday", timestamp, timezone=zone).precision == "deferred"
    )


def test_negation_units_and_identifiers_are_preserved():
    text = "We did not switch db_v1.sqlite or the 64 MB limit yesterday."
    result = normalize_relative(text, source(), timezone="Asia/Kolkata")
    assert result.text == "We did not switch db_v1.sqlite or the 64 MB limit 2026-10-14."
    assert (
        normalize_relative("Use logs/yesterday.json and yesterday_id", source()).precision
        == "unchanged"
    )


@pytest.mark.parametrize("phrase", ["yday", "one day ago", "1 day ago", "a day ago"])
def test_relative_aliases(phrase):
    assert (
        str(normalize_relative(phrase, source(), timezone="Asia/Kolkata").start_date)
        == "2026-10-14"
    )


def test_exact_time_is_resolved_only_with_explicit_clock_and_timezone():
    result = normalize_relative("Switched yesterday at 09:30", source(), timezone="Asia/Kolkata")
    assert result.instant.isoformat() == "2026-10-14T04:00:00+00:00"
    assert result.precision == "instant"


@pytest.mark.parametrize(
    "timestamp,text",
    [
        ("2026-11-02T12:00:00+00:00", "Switched yesterday at 01:30"),
        ("2026-03-09T12:00:00+00:00", "Switched yesterday at 02:30"),
    ],
)
def test_dst_fold_and_gap_are_ambiguous(timestamp, text):
    assert (
        normalize_relative(text, source(timestamp), timezone="America/New_York").precision
        == "deferred"
    )


@pytest.mark.parametrize(
    "text",
    [
        "Switched last month",
        "Switched two days ago",
        "Switched 3 hours ago",
        "Switched next year",
        "Switched " + "9" * 5000 + " days ago",
    ],
)
def test_unsupported_relative_time_or_unbounded_number_defers(text):
    assert normalize_relative(text, source(), timezone="UTC").precision == "deferred"

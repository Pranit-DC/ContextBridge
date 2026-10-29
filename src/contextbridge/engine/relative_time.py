"""Source-relative temporal interpretation, with explicit precision and no receipt-time fallback.

V1 candidates require an instant. A calendar date/range is useful normalization output, but
cannot authorize an exact effective timestamp; the write boundary defers that candidate.
"""

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

PHRASE = re.compile(
    r"(?<![\w./-])(yesterday|yday|today|last week|(?:\d+|a|one) (?:days?|weeks?) ago)"
    r"(?![\w/-]|\.\w)",
    re.I,
)
VAGUE = re.compile(
    r"\b(recently|last (?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
    r"|the other day|a while ago|tomorrow|next week)\b",
    re.I,
)
UNCERTAIN = re.compile(
    r"\b(maybe|perhaps|might|possibly|probably|roughly|approximately|about|around)\b", re.I
)
CLOCK = re.compile(r"\s+at\s+(\d{1,2}):(\d{2})(?:\s*(am|pm))?\b", re.I)


@dataclass(frozen=True)
class TemporalResolution:
    text: str
    precision: str
    start_date: date | None = None
    end_date: date | None = None  # exclusive, for ranges
    instant: datetime | None = None
    reason: str | None = None


def normalize_relative(text, occurred_at, *, timezone=None):
    """Use the interaction's justified source instant and explicit source-zone binding.

    The timezone is mandatory even when occurred_at is UTC: V1 wire parsing has already
    erased the original offset. No current/receipt time is consulted. Dates stay dates.
    """
    matches = list(PHRASE.finditer(text))
    if not matches and not VAGUE.search(text):
        return TemporalResolution(text, "unchanged")
    deferred = TemporalResolution(text, "deferred", reason="AMBIGUOUS_TIME")
    if len(matches) != 1 or VAGUE.search(text) or UNCERTAIN.search(text):
        return deferred
    if occurred_at is None or occurred_at.tzinfo is None or timezone is None:
        return deferred
    try:
        zone = ZoneInfo(timezone)
        source_date = occurred_at.astimezone(zone).date()
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return deferred
    match = matches[0]
    phrase = match.group().lower()
    end = None
    if phrase in {"yesterday", "yday", "today"}:
        start = source_date - timedelta(days=phrase != "today")
    elif phrase == "last week":
        end = source_date - timedelta(days=source_date.weekday())
        start = end - timedelta(days=7)
    else:
        count, unit, _ = phrase.split()
        number = 1 if count in {"a", "one"} else int(count)
        if number > 36_500:
            return deferred
        try:
            start = source_date - timedelta(days=number * (7 if unit.startswith("week") else 1))
        except OverflowError:
            return deferred
    clock = CLOCK.match(text, match.end())
    if clock is not None:
        if end is not None:
            return deferred
        hour, minute = int(clock[1]), int(clock[2])
        meridiem = clock[3]
        if hour > 23 or minute > 59 or (meridiem and not 1 <= hour <= 12):
            return deferred
        if meridiem:
            hour = hour % 12 + (12 if meridiem.lower() == "pm" else 0)
        local = datetime(start.year, start.month, start.day, hour, minute, tzinfo=zone)
        # Reject repeated/nonexistent local wall times instead of choosing a DST fold.
        if local.utcoffset() != local.replace(fold=1).utcoffset():
            return deferred
        if local.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != local.replace(
            tzinfo=None
        ):
            return deferred
        if local > occurred_at:
            return deferred
        absolute = f"{start.isoformat()} at {hour:02}:{minute:02} ({timezone})"
        return TemporalResolution(
            text[: match.start()] + absolute + text[clock.end() :],
            "instant",
            start,
            instant=local.astimezone(UTC),
        )
    absolute = (
        start.isoformat()
        if end is None
        else f"{start.isoformat()} through {(end - timedelta(days=1)).isoformat()}"
    )
    return TemporalResolution(
        text[: match.start()] + absolute + text[match.end() :],
        "date" if end is None else "date_range",
        start,
        end,
    )


def review_candidates(event, candidates, *, timezone=None):
    """Defer unrepresentable relative dates; apply only justified exact source times.

    Never rewrite evidence, negation, aliases, units, identifiers or candidate conditions.
    Formation still owns semantic support and content normalization.
    """
    accepted, deferred = [], False
    for candidate in candidates:
        resolution = normalize_relative(
            candidate.source.evidence, event.occurred_at, timezone=timezone
        )
        if resolution.precision in {"deferred", "date", "date_range"}:
            deferred = True
            continue
        if resolution.instant is not None:
            candidate = candidate.model_copy(update={"valid_from": resolution.instant})
        accepted.append(candidate)
    return accepted, deferred

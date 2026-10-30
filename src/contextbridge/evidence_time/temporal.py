"""Conservative guaranteed applicability, not invented exact transition times."""

import re
from datetime import UTC, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from contextbridge.engine.errors import ModuleError
from contextbridge.engine.relative_time import normalize_relative
from contextbridge.evidence_time.contracts import TemporalBounds


class TemporalAmbiguity(Exception):
    """Internal safe deferral, not a provider/HTTP failure."""


DATE = re.compile(r"(?<![\w./-])(\d{4}-\d{2}-\d{2})(?![\w/-]|\.\w|T\d)")
INSTANT = re.compile(
    r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:\d{2})"
)


def midnight(value, zone):
    local = datetime.combine(value, time.min, tzinfo=zone)
    if local.utcoffset() != local.replace(fold=1).utcoffset() or local.astimezone(UTC).astimezone(
        zone
    ).replace(tzinfo=None) != local.replace(tzinfo=None):
        raise TemporalAmbiguity()
    return local.astimezone(UTC)


def one_fragment(quote, trace, relation):
    observed = datetime.fromisoformat(trace["occurred_at"])
    zone = ZoneInfo(trace["source_timezone"])
    resolved = normalize_relative(quote, observed, timezone=trace["source_timezone"])
    if resolved.precision == "deferred":
        raise TemporalAmbiguity()
    precision = "instant"
    lower = latest = upper = observed.astimezone(UTC)
    if resolved.instant is not None:
        lower = latest = upper = resolved.instant
    elif resolved.start_date is not None:
        start = resolved.start_date
        end = resolved.end_date or start + timedelta(days=1)
        lower = midnight(start, zone)
        latest = midnight(end, zone)
        upper = min(latest, observed.astimezone(UTC))
        precision = (
            "week"
            if re.search(r"\blast week\b", quote, re.I)
            else ("range" if resolved.end_date else "day")
        )
    else:
        instants = INSTANT.findall(quote)
        dates = DATE.findall(quote)
        if len(instants) > 1:
            raise TemporalAmbiguity()
        if instants:
            lower = latest = upper = datetime.fromisoformat(instants[0]).astimezone(UTC)
        elif dates:
            if len(dates) > 2:
                raise TemporalAmbiguity()
            start = datetime.strptime(dates[0], "%Y-%m-%d").date()
            if len(dates) == 2:
                if not re.search(r"\b(?:between|through)\b", quote, re.I):
                    raise TemporalAmbiguity()
                end = datetime.strptime(dates[1], "%Y-%m-%d").date() + timedelta(days=1)
                precision = "range"
            else:
                end = start + timedelta(days=1)
                precision = "day"
            lower = midnight(start, zone)
            latest = midnight(end, zone)
        upper = min(latest, observed.astimezone(UTC))
    if relation == "context_only":
        upper = observed.astimezone(UTC)
    if lower > latest or (relation != "context_only" and (lower > upper or upper > observed)):
        raise TemporalAmbiguity()
    return TemporalBounds(
        precision=precision,
        relation=relation,
        earliest=lower,
        latest=latest,
        guaranteed_from=upper,
        source_timezone=trace["source_timezone"],
        source_event_id=UUID(trace["event_id"]),
        normalized_evidence=resolved.text,
    )


def bounds(fragments, mapping, relation):
    values = []
    try:
        for fragment in fragments:
            quote = fragment["quote"]
            trace = mapping[fragment["message_id"]]
            result = one_fragment(quote, trace, relation)
            if (
                result.precision != "instant"
                or INSTANT.search(quote)
                or result.earliest != datetime.fromisoformat(trace["occurred_at"])
            ):
                values.append(result)
        if not values:
            fragment = max(
                fragments,
                key=lambda f: datetime.fromisoformat(mapping[f["message_id"]]["occurred_at"]),
            )
            return one_fragment(fragment["quote"], mapping[fragment["message_id"]], relation)
        if any(
            (v.precision, v.earliest, v.latest, v.guaranteed_from)
            != (
                values[0].precision,
                values[0].earliest,
                values[0].latest,
                values[0].guaranteed_from,
            )
            for v in values
        ):
            raise TemporalAmbiguity()
        if relation == "context_only":
            latest_observation = max(
                datetime.fromisoformat(mapping[f["message_id"]]["occurred_at"]) for f in fragments
            )
            return values[0].model_copy(
                update={"guaranteed_from": latest_observation.astimezone(UTC)}
            )
        return values[0]
    except (ValueError, TypeError, KeyError, OverflowError):
        raise ModuleError("INVALID_PROVIDER_OUTPUT") from None


def qualify(content, temporal):
    if temporal.precision == "instant":
        return content
    label = (
        "Source time reference"
        if temporal.relation == "context_only"
        else "Uncertain occurrence window"
    )
    return (
        content
        + "\n"
        + label
        + ": ["
        + temporal.earliest.isoformat()
        + ", "
        + temporal.latest.isoformat()
        + "]; precision="
        + temporal.precision
        + ", timezone="
        + temporal.source_timezone
        + ". Established by "
        + temporal.guaranteed_from.isoformat()
        + "; exact occurrence time is not asserted."
    )

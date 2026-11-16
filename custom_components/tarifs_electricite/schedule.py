"""Pure standard-library tariff engine; no Home Assistant dependency.

A day selected on a cross-midnight rule means the day on which the rule
STARTS.  E.g. Monday 22:30-06:30 covers Tuesday 00:00-06:30 as well.
Intervals are [start, end); adjacent intervals are allowed.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .const import (
    CONF_DAYS, CONF_END, CONF_START, MAX_DAILY_RULES, MAX_PRICE, MAX_RULES,
)

MINUTES_PER_DAY = 1440
MINUTES_PER_WEEK = 10080
PRICE_QUANTUM = Decimal("0.0001")


class TariffValidationError(ValueError):
    """Validation error with a translation-compatible short code."""


def normalize_price(value: object) -> str:
    """Validate and serialize prices as exact four-decimal strings."""
    try:
        price = Decimal(str(value).strip().replace(",", "."))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise TariffValidationError("invalid_price") from exc
    if not price.is_finite() or not Decimal("0") <= price <= MAX_PRICE:
        raise TariffValidationError("invalid_price")
    return format(price.quantize(PRICE_QUANTUM, rounding=ROUND_HALF_UP), ".4f")


def normalize_timezone(value: str) -> str:
    """Validate an IANA timezone (not a numeric UTC offset)."""
    if not isinstance(value, str) or not value.strip():
        raise TariffValidationError("invalid_timezone")
    try:
        ZoneInfo(value.strip())
    except (ValueError, ZoneInfoNotFoundError, KeyError) as exc:
        raise TariffValidationError("invalid_timezone") from exc
    return value.strip()


def normalize_clock(value: object) -> str:
    """Accept HH:MM or Home Assistant's HH:MM:SS selector values."""
    try:
        parsed = value if isinstance(value, time) else time.fromisoformat(str(value))
    except (ValueError, TypeError) as exc:
        raise TariffValidationError("invalid_time") from exc
    if parsed.tzinfo is not None or parsed.second or parsed.microsecond:
        raise TariffValidationError("invalid_time")
    return parsed.strftime("%H:%M")


def minute_of_day(value: str) -> int:
    hours, minutes = (int(part) for part in value.split(":"))
    return hours * 60 + minutes


def normalize_rule(raw_rule: dict) -> dict:
    """Validate one rule and produce a JSON-serializable representation."""
    try:
        start = normalize_clock(raw_rule[CONF_START])
        end = normalize_clock(raw_rule[CONF_END])
        days_in = raw_rule[CONF_DAYS]
    except (KeyError, TypeError) as exc:
        raise TariffValidationError("invalid_period") from exc
    if start == end:
        raise TariffValidationError("same_times")
    if not isinstance(days_in, (list, tuple, set)) or not days_in:
        raise TariffValidationError("invalid_days")
    try:
        days = sorted({int(value) for value in days_in})
    except (TypeError, ValueError) as exc:
        raise TariffValidationError("invalid_days") from exc
    if not days or any(day < 0 or day > 6 for day in days):
        raise TariffValidationError("invalid_days")
    return {CONF_START: start, CONF_END: end, CONF_DAYS: days}


def validate_rules(rules: list[dict]) -> list[dict]:
    """Reject overlap across midnight, Sunday/Monday, and weekday variants."""
    if len(rules) > MAX_RULES:
        raise TariffValidationError("too_many_periods")
    normalized = [normalize_rule(raw) for raw in rules]
    per_day_count = [0] * 7
    weekly_intervals: list[tuple[int, int]] = []
    for rule in normalized:
        start = minute_of_day(rule[CONF_START])
        end = minute_of_day(rule[CONF_END])
        for day in rule[CONF_DAYS]:
            per_day_count[day] += 1
            if per_day_count[day] > MAX_DAILY_RULES:
                raise TariffValidationError("too_many_periods_per_day")
            begin = day * MINUTES_PER_DAY + start
            finish = day * MINUTES_PER_DAY + end
            if end <= start:
                finish += MINUTES_PER_DAY
            if finish <= MINUTES_PER_WEEK:
                weekly_intervals.append((begin, finish))
            else:
                weekly_intervals.extend(
                    [(begin, MINUTES_PER_WEEK), (0, finish - MINUTES_PER_WEEK)]
                )
    weekly_intervals.sort()
    for previous, current in zip(weekly_intervals, weekly_intervals[1:]):
        if previous[1] > current[0]:
            raise TariffValidationError("overlapping_period")
    return normalized


def is_heure_creuse(
    rules: list[dict], local_now: datetime, full_day_hc: frozenset[int] = frozenset()
) -> bool:
    """Evaluate rules plus days designated HC from 00:00 inclusive to next 00:00.

    Full-day settings are independent of the 4 ordinary periods per day. They
    form the union with periods, so an existing HC period never switches back
    to HP in the middle of a selected full-day date.
    """
    day = local_now.weekday()
    if day in full_day_hc:
        return True
    minute = local_now.hour * 60 + local_now.minute
    previous_day = (day - 1) % 7
    for rule in rules:
        start = minute_of_day(rule[CONF_START])
        end = minute_of_day(rule[CONF_END])
        days = rule[CONF_DAYS]
        if start < end:
            if day in days and start <= minute < end:
                return True
        elif (day in days and minute >= start) or (
            previous_day in days and minute < end
        ):
            return True
    return False


def next_tariff_transition(
    rules: list[dict], tz_name: str, now_utc: datetime,
    full_day_hc: frozenset[int] = frozenset(),
) -> datetime | None:
    """Return the next ACTUAL state change in UTC (or None if always same).

    Scan future UTC minute instants, not naïve local datetimes. This correctly
    handles missing and repeated civil times at DST transitions, and handles
    schedules where an end immediately meets another start. Only computed
    when settings change or a boundary fires; no recurring polling job.
    """
    if now_utc.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware")
    if not rules and not full_day_hc:
        return None
    utc_now = now_utc.astimezone(timezone.utc)
    tz = ZoneInfo(tz_name)
    old_state = is_heure_creuse(rules, utc_now.astimezone(tz), full_day_hc)
    instant = utc_now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(MINUTES_PER_WEEK + 2 * MINUTES_PER_DAY + 1):
        state = is_heure_creuse(rules, instant.astimezone(tz), full_day_hc)
        if state != old_state:
            return instant
        instant += timedelta(minutes=1)
    return None

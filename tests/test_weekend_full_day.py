"""Weekend HC all-day regression tests (Europe/Paris local civil days)."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

PARIS = ZoneInfo("Europe/Paris")
SATURDAY = frozenset({5})
SUNDAY = frozenset({6})
WEEKEND = frozenset({5, 6})


def local(y, m, d, hour, minute=0, fold=0):
    return datetime(y, m, d, hour, minute, tzinfo=PARIS, fold=fold)


def utc(value):
    return value.astimezone(timezone.utc)


def rule(start, end, days):
    return {"start": start, "end": end, "days": days}


@pytest.mark.parametrize("day, hour, expected", [
    (20, 23, False),  # Friday
    (21, 0, True),  # Saturday midnight
    (21, 12, True),
    (21, 23, True),
    (22, 0, True),  # Sunday midnight is not a transition
    (22, 12, True),
    (22, 23, True),
    (23, 0, False),  # Monday midnight
])
def test_entire_weekend(engine, day, hour, expected):
    assert engine.is_heure_creuse([], local(2026, 11, day, hour), WEEKEND) is expected


def test_independent_saturday_switch(engine):
    assert engine.is_heure_creuse([], local(2026, 11, 21, 12), SATURDAY)
    assert not engine.is_heure_creuse([], local(2026, 11, 22, 12), SATURDAY)
    assert engine.next_tariff_transition([], "Europe/Paris", utc(local(2026, 11, 21, 22)), SATURDAY) == utc(local(2026, 11, 22, 0))


def test_independent_sunday_switch(engine):
    assert not engine.is_heure_creuse([], local(2026, 11, 21, 12), SUNDAY)
    assert engine.is_heure_creuse([], local(2026, 11, 22, 12), SUNDAY)
    assert engine.next_tariff_transition([], "Europe/Paris", utc(local(2026, 11, 21, 22)), SUNDAY) == utc(local(2026, 11, 22, 0))


def test_entire_weekend_next_transitions(engine):
    assert engine.next_tariff_transition([], "Europe/Paris", utc(local(2026, 11, 20, 23, 59)), WEEKEND) == utc(local(2026, 11, 21, 0))
    assert engine.next_tariff_transition([], "Europe/Paris", utc(local(2026, 11, 21, 12)), WEEKEND) == utc(local(2026, 11, 23, 0))
    assert engine.next_tariff_transition([], "Europe/Paris", utc(local(2026, 11, 23, 0)), WEEKEND) == utc(local(2026, 11, 28, 0))


def test_existing_weekday_schedule_unchanged(engine):
    rules = engine.validate_rules([rule("12:30", "14:30", [0, 1, 2, 3, 4])])
    assert engine.is_heure_creuse(rules, local(2026, 11, 20, 13), WEEKEND)
    assert not engine.is_heure_creuse(rules, local(2026, 11, 20, 15), WEEKEND)
    assert engine.is_heure_creuse(rules, local(2026, 11, 21, 16), WEEKEND)
    assert not engine.is_heure_creuse(rules, local(2026, 11, 23, 11), WEEKEND)


def test_friday_night_does_not_cause_saturday_morning_transition(engine):
    rules = engine.validate_rules([rule("22:30", "06:30", [4])])
    assert engine.is_heure_creuse(rules, local(2026, 11, 21, 6, 30), WEEKEND)
    assert engine.next_tariff_transition(rules, "Europe/Paris", utc(local(2026, 11, 20, 23)), WEEKEND) == utc(local(2026, 11, 23, 0))


def test_sunday_night_can_continue_into_monday(engine):
    rules = engine.validate_rules([rule("22:30", "06:30", [6])])
    assert engine.is_heure_creuse(rules, local(2026, 11, 23, 0), WEEKEND)
    assert engine.is_heure_creuse(rules, local(2026, 11, 23, 6, 29), WEEKEND)
    assert not engine.is_heure_creuse(rules, local(2026, 11, 23, 6, 30), WEEKEND)
    assert engine.next_tariff_transition(rules, "Europe/Paris", utc(local(2026, 11, 22, 12)), WEEKEND) == utc(local(2026, 11, 23, 6, 30))


def test_weekend_overrides_existing_timed_rule_even_when_same_hours(engine):
    # No conflict is created by marking a complete day as HC; existing rules
    # already represent HC, so the union is still always HC.
    rules = engine.validate_rules([rule("12:30", "14:30", [5, 6])])
    assert engine.is_heure_creuse(rules, local(2026, 11, 21, 12), WEEKEND)
    assert engine.is_heure_creuse(rules, local(2026, 11, 21, 14, 30), WEEKEND)
    assert engine.next_tariff_transition(rules, "Europe/Paris", utc(local(2026, 11, 21, 13)), WEEKEND) == utc(local(2026, 11, 23, 0))


def test_weekend_dst_spring_short_sunday(engine):
    # DST makes Sunday 2026-03-29 last 23 real hours but a complete local day.
    assert engine.is_heure_creuse([], local(2026, 3, 29, 1, 59), WEEKEND)
    assert engine.is_heure_creuse([], local(2026, 3, 29, 3, 0), WEEKEND)
    assert engine.next_tariff_transition([], "Europe/Paris", utc(local(2026, 3, 29, 0, 0)), WEEKEND) == utc(local(2026, 3, 30, 0, 0))


def test_weekend_dst_fall_long_sunday(engine):
    # DST makes Sunday 2026-10-25 last 25 real hours.
    assert engine.is_heure_creuse([], local(2026, 10, 25, 2, 30, fold=0), WEEKEND)
    assert engine.is_heure_creuse([], local(2026, 10, 25, 2, 30, fold=1), WEEKEND)
    assert engine.next_tariff_transition([], "Europe/Paris", utc(local(2026, 10, 25, 1, 30)), WEEKEND) == utc(local(2026, 10, 26, 0, 0))


def test_weekend_flag_switching_does_not_change_timed_rules(engine):
    rules = engine.validate_rules([rule("12:30", "14:30", [5])])
    assert not engine.is_heure_creuse(rules, local(2026, 11, 21, 9))
    assert engine.is_heure_creuse(rules, local(2026, 11, 21, 9), SATURDAY)
    assert not engine.is_heure_creuse(rules, local(2026, 11, 21, 9))

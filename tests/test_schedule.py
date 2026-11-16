"""Unit tests for all local-time and DST tariff transitions."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest


PARIS = ZoneInfo("Europe/Paris")


def rule(start, end, days=range(7)):
    return {"start": start, "end": end, "days": list(days)}


def local(y, month, d, h, minute=0, fold=0):
    return datetime(y, month, d, h, minute, tzinfo=PARIS, fold=fold)


def test_prices_preserve_four_decimals(engine):
    assert engine.normalize_price("0.19") == "0.1900"
    assert engine.normalize_price("0,2500") == "0.2500"
    assert engine.normalize_price("0.123456") == "0.1235"
    assert engine.normalize_price(0) == "0.0000"


@pytest.mark.parametrize("value", [-1, 11, "nan", "inf", "abc", None])
def test_invalid_prices(engine, value):
    with pytest.raises(engine.TariffValidationError):
        engine.normalize_price(value)


def test_timezone(engine):
    assert engine.normalize_timezone("Europe/Paris") == "Europe/Paris"
    with pytest.raises(engine.TariffValidationError):
        engine.normalize_timezone("Paris")


def test_clock_selector_times(engine):
    assert engine.normalize_clock("22:30:00") == "22:30"
    assert engine.normalize_clock("06:30") == "06:30"
    with pytest.raises(engine.TariffValidationError):
        engine.normalize_clock("22:30:30")
    with pytest.raises(engine.TariffValidationError):
        engine.normalize_clock("24:01")


def test_two_periods_expected_transitions(engine):
    rules = engine.validate_rules([rule("22:30", "06:30"), rule("12:30", "14:30")])
    assert not engine.is_heure_creuse(rules, local(2026, 11, 16, 22, 29))
    assert engine.is_heure_creuse(rules, local(2026, 11, 16, 22, 30))
    assert engine.is_heure_creuse(rules, local(2026, 11, 17, 6, 29))
    assert not engine.is_heure_creuse(rules, local(2026, 11, 17, 6, 30))
    assert engine.is_heure_creuse(rules, local(2026, 11, 17, 12, 30))
    assert not engine.is_heure_creuse(rules, local(2026, 11, 17, 14, 30))


def test_weekday_ownership_for_cross_midnight(engine):
    monday_only = engine.validate_rules([rule("22:30", "06:30", [0])])
    assert engine.is_heure_creuse(monday_only, local(2026, 11, 16, 23))
    assert engine.is_heure_creuse(monday_only, local(2026, 11, 17, 5))
    assert not engine.is_heure_creuse(monday_only, local(2026, 11, 18, 5))


def test_sunday_to_monday_overlap_rejected(engine):
    with pytest.raises(engine.TariffValidationError, match="overlapping_period"):
        engine.validate_rules([rule("23:00", "02:00", [6]), rule("01:00", "03:00", [0])])


def test_adjacency_allowed(engine):
    assert len(engine.validate_rules([
        rule("22:00", "00:00", [0]), rule("00:00", "02:00", [1])
    ])) == 2


def test_cross_midnight_overlap_rejected(engine):
    with pytest.raises(engine.TariffValidationError, match="overlapping_period"):
        engine.validate_rules([rule("22:30", "06:30", [0]), rule("06:00", "07:00", [1])])


def test_duplicate_and_same_day_rejected(engine):
    with pytest.raises(engine.TariffValidationError, match="overlapping_period"):
        engine.validate_rules([rule("11:00", "12:00", [0]), rule("11:00", "12:00", [0])])
    with pytest.raises(engine.TariffValidationError, match="same_times"):
        engine.validate_rules([rule("12:00", "12:00")])


def test_four_per_weekday_and_different_weekday_rules(engine):
    periods = [rule(f"{hour:02}:00", f"{hour+1:02}:00", [0]) for hour in (0, 3, 6, 9)]
    periods += [rule("00:00", "01:00", [day]) for day in range(1, 7)]
    assert len(engine.validate_rules(periods)) == 10
    with pytest.raises(engine.TariffValidationError, match="too_many_periods_per_day"):
        engine.validate_rules(periods + [rule("12:00", "13:00", [0])])


def test_no_weekday_or_fifth_day_not_accepted(engine):
    with pytest.raises(engine.TariffValidationError, match="invalid_days"):
        engine.validate_rules([rule("10:00", "12:00", [])])
    with pytest.raises(engine.TariffValidationError, match="invalid_days"):
        engine.validate_rules([rule("10:00", "12:00", [7])])


def test_no_rules_no_transition(engine):
    assert engine.next_tariff_transition([], "Europe/Paris", local(2026, 11, 16, 12)) is None


def test_next_transition_in_utc(engine):
    rules = engine.validate_rules([rule("22:30", "06:30")])
    now = local(2026, 11, 16, 22, 20).astimezone(timezone.utc)
    assert engine.next_tariff_transition(rules, "Europe/Paris", now) == local(2026, 11, 16, 22, 30).astimezone(timezone.utc)


def test_next_transition_when_currently_hc(engine):
    rules = engine.validate_rules([rule("22:30", "06:30")])
    now = local(2026, 11, 17, 2).astimezone(timezone.utc)
    assert engine.next_tariff_transition(rules, "Europe/Paris", now) == local(2026, 11, 17, 6, 30).astimezone(timezone.utc)


def test_transition_when_intervals_are_contiguous(engine):
    rules = engine.validate_rules([
        rule("09:00", "12:00"), rule("12:00", "17:00")
    ])
    now = local(2026, 11, 16, 10).astimezone(timezone.utc)
    assert engine.next_tariff_transition(rules, "Europe/Paris", now) == local(2026, 11, 16, 17).astimezone(timezone.utc)


def test_dst_spring_gap_triggers_at_first_real_local_minute(engine):
    # In Paris 02:00-02:59 does not exist on 2026-03-29.
    rules = engine.validate_rules([rule("02:30", "04:00", [6])])
    before = datetime(2026, 3, 29, 0, 50, tzinfo=timezone.utc)
    assert engine.next_tariff_transition(rules, "Europe/Paris", before) == datetime(
        2026, 3, 29, 1, 0, tzinfo=timezone.utc
    )
    assert engine.is_heure_creuse(rules, datetime(2026, 3, 29, 1, 0, tzinfo=timezone.utc).astimezone(PARIS))


def test_dst_fall_back_repeated_hour(engine):
    # In Paris 02:00-02:59 occurs twice on 2026-10-25.
    rules = engine.validate_rules([rule("02:30", "03:30", [6])])
    first = local(2026, 10, 25, 2, 30, fold=0)
    second_hour_start = local(2026, 10, 25, 2, 0, fold=1)
    repeated = local(2026, 10, 25, 2, 30, fold=1)
    assert engine.is_heure_creuse(rules, first)
    assert not engine.is_heure_creuse(rules, second_hour_start)
    assert engine.is_heure_creuse(rules, repeated)
    assert engine.next_tariff_transition(rules, "Europe/Paris", first.astimezone(timezone.utc)) == second_hour_start.astimezone(timezone.utc)
    assert engine.next_tariff_transition(rules, "Europe/Paris", second_hour_start.astimezone(timezone.utc)) == repeated.astimezone(timezone.utc)


def test_overnight_across_dst_fall_back(engine):
    rules = engine.validate_rules([rule("22:30", "06:30", [5])])
    assert engine.is_heure_creuse(rules, local(2026, 10, 25, 2, 15, fold=0))
    assert engine.is_heure_creuse(rules, local(2026, 10, 25, 2, 15, fold=1))


def test_day_rule_not_active_on_unselected_day(engine):
    rules = engine.validate_rules([rule("11:00", "13:00", [0])])
    assert engine.is_heure_creuse(rules, local(2026, 11, 16, 12))
    assert not engine.is_heure_creuse(rules, local(2026, 11, 17, 12))

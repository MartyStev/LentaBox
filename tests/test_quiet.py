from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

import pytest

from core import quiet


def test_parse_window():
    assert quiet.parse_window("23:00-08:00") == (time(23, 0), time(8, 0))
    assert quiet.parse_window(" 9:5 - 17:30 ") is None            # strict HH:MM: no guessing
    assert quiet.parse_window("09:05-17:30") == (time(9, 5), time(17, 30))
    assert quiet.parse_window("") is None
    assert quiet.parse_window("off") is None


@pytest.mark.parametrize("text", ["25:00-08:00", "23:00-24:01", "23:00", "23:00-23:00", "abc", "23:00-08:00-09:00"])
def test_parse_window_rejects_bad_input(text):
    with pytest.raises(ValueError):
        quiet.parse_window_strict(text)


def test_strict_parser_treats_empty_and_off_as_disabled():
    assert quiet.parse_window_strict("") is None
    assert quiet.parse_window_strict("off") is None
    assert quiet.parse_window_strict("OFF") is None
    assert quiet.parse_window_strict("23:00-08:00") == (time(23, 0), time(8, 0))


MOSCOW = ZoneInfo("Europe/Moscow")


def at(hour, minute=0, tz=UTC):
    return datetime(2026, 10, 15, hour, minute, tzinfo=tz)


def test_overnight_window_covers_midnight():
    window = (time(23, 0), time(8, 0))
    assert quiet.in_quiet(at(23, 0), window, UTC)
    assert quiet.in_quiet(at(3), window, UTC)
    assert quiet.in_quiet(at(7, 59), window, UTC)
    assert not quiet.in_quiet(at(8, 0), window, UTC)              # end is exclusive
    assert not quiet.in_quiet(at(12), window, UTC)
    assert not quiet.in_quiet(at(22, 59), window, UTC)


def test_same_day_window():
    window = (time(13, 0), time(15, 0))
    assert quiet.in_quiet(at(13), window, UTC)
    assert not quiet.in_quiet(at(15), window, UTC)
    assert not quiet.in_quiet(at(12, 59), window, UTC)


def test_window_is_evaluated_in_the_configured_timezone():
    window = (time(23, 0), time(8, 0))
    # 21:30 UTC is 00:30 in Moscow (UTC+3): quiet there, not in UTC
    assert quiet.in_quiet(at(21, 30), window, MOSCOW)
    assert not quiet.in_quiet(at(21, 30), window, UTC)


def test_no_window_is_never_quiet():
    assert not quiet.in_quiet(at(3), None, UTC)


def test_naive_datetime_is_treated_as_utc():
    assert quiet.in_quiet(datetime(2026, 10, 15, 3, 0), (time(23, 0), time(8, 0)), UTC)


def test_format_window_roundtrip():
    window = quiet.parse_window_strict("23:00-08:00")
    assert quiet.format_window(window) == "23:00-08:00"
    assert quiet.format_window(None) == ""

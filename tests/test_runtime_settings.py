from datetime import time
from zoneinfo import ZoneInfo

import pytest

import config
from core import runtime


@pytest.fixture(autouse=True)
def reset_settings():
    yield
    for name in ("delivery_mode", "digest_hours", "quiet_hours", "timezone"):
        runtime.reset(name)


def test_defaults_come_from_config():
    assert runtime.get("delivery_mode") == config.DELIVERY_MODE == "instant"
    assert runtime.get("digest_hours") == config.DIGEST_HOURS
    assert runtime.get("quiet_hours") == config.QUIET_HOURS == ""
    assert runtime.get("timezone") == config.TIMEZONE


def test_delivery_mode_accepts_only_known_values():
    assert runtime.parse("delivery_mode", " Digest ") == "digest"
    assert runtime.parse("delivery_mode", "instant") == "instant"
    with pytest.raises(ValueError):
        runtime.parse("delivery_mode", "hourly")


def test_digest_hours_is_a_bounded_integer():
    assert runtime.parse("digest_hours", "6") == 6
    for bad in ("0", "25", "abc"):
        with pytest.raises(ValueError):
            runtime.parse("digest_hours", bad)


def test_quiet_hours_are_normalised_and_off_clears_them():
    assert runtime.parse("quiet_hours", " 23:00-08:00 ") == "23:00-08:00"
    assert runtime.parse("quiet_hours", "off") == ""
    with pytest.raises(ValueError):
        runtime.parse("quiet_hours", "late at night")


def test_timezone_must_be_a_known_iana_name():
    assert runtime.parse("timezone", "Europe/Moscow") == "Europe/Moscow"
    with pytest.raises(ValueError):
        runtime.parse("timezone", "Mars/Olympus")


def test_helpers_expose_parsed_values():
    runtime.set_value("quiet_hours", "22:30-07:00")
    runtime.set_value("timezone", "Europe/Moscow")
    assert runtime.quiet_window() == (time(22, 30), time(7, 0))
    assert runtime.zone() == ZoneInfo("Europe/Moscow")
    runtime.set_value("quiet_hours", "off")
    assert runtime.quiet_window() is None


def test_stored_garbage_is_ignored_on_load():
    runtime.load({"delivery_mode": "weird", "digest_hours": "99", "quiet_hours": "x", "timezone": "Nope/Nope"})
    assert runtime.get("delivery_mode") == "instant"
    assert runtime.get("digest_hours") == config.DIGEST_HOURS
    assert runtime.get("quiet_hours") == ""

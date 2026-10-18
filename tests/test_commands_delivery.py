"""Owner commands for delivery: /mode, /digest, /quiet, /tz."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from core import i18n, runtime
from handlers import commands


class FakeClient:
    def __init__(self):
        self.handlers = []

    def on(self, builder):
        def register(handler):
            self.handlers.append((builder, handler))
            return handler
        return register

    def match(self, text):
        for builder, handler in self.handlers:
            match = builder.pattern(text)
            if match:
                return handler, match
        raise AssertionError(f"No command matches {text!r}")


@pytest.fixture(autouse=True)
def english_and_clean_settings():
    runtime.set_value("language", "en")
    yield
    for name in ("language", "delivery_mode", "digest_hours", "quiet_hours", "timezone"):
        runtime.reset(name)


async def call(text, flush=None, queued=0):
    client = FakeClient()
    commands.register_commands(client, 2, flush_digest=flush)
    handler, match = client.match(text)
    event = SimpleNamespace(pattern_match=match, reply=AsyncMock())
    with patch.object(commands.settings_db, "save") as save, \
         patch.object(commands.digest_db, "count_unsent", return_value=queued):
        await handler(event)
    return event.reply.await_args.args[0], save


async def test_mode_shows_current_value():
    reply, save = await call("/mode")
    assert "instant" in reply and "/mode digest" in reply
    save.assert_not_called()


async def test_mode_switches_and_persists():
    reply, save = await call("/mode digest")
    assert runtime.get("delivery_mode") == "digest"
    save.assert_called_once_with("delivery_mode", "digest")
    assert reply.startswith("✅") and "digest" in reply


async def test_mode_rejects_unknown_value():
    reply, save = await call("/mode hourly")
    assert reply.startswith("❌")
    save.assert_not_called()
    assert runtime.get("delivery_mode") == "instant"


async def test_digest_without_argument_shows_period_and_queue_size():
    reply, _ = await call("/digest", queued=7)
    assert "3" in reply and "7" in reply


async def test_digest_sets_the_period():
    reply, save = await call("/digest 6")
    assert runtime.get("digest_hours") == 6
    save.assert_called_once_with("digest_hours", 6)
    assert reply.startswith("✅")


async def test_digest_rejects_out_of_range_period():
    reply, save = await call("/digest 99")
    assert reply.startswith("❌")
    save.assert_not_called()


async def test_digest_now_flushes_the_queue():
    flush = AsyncMock(return_value=5)
    reply, _ = await call("/digest now", flush=flush)
    flush.assert_awaited_once()
    assert "5" in reply and reply.startswith("✅")


async def test_digest_now_with_empty_queue_says_so():
    reply, _ = await call("/digest now", flush=AsyncMock(return_value=0))
    assert "empty" in reply.lower()


async def test_quiet_shows_off_by_default_and_sets_and_clears():
    reply, _ = await call("/quiet")
    assert "off" in reply.lower() or "/quiet 23:00-08:00" in reply

    reply, save = await call("/quiet 23:00-08:00")
    assert runtime.get("quiet_hours") == "23:00-08:00"
    save.assert_called_once_with("quiet_hours", "23:00-08:00")
    assert "23:00-08:00" in reply

    reply, save = await call("/quiet off")
    assert runtime.get("quiet_hours") == ""
    save.assert_called_once_with("quiet_hours", "")


async def test_quiet_rejects_garbage():
    reply, save = await call("/quiet late")
    assert reply.startswith("❌") and "HH:MM-HH:MM" in reply
    save.assert_not_called()


async def test_timezone_is_shown_set_and_validated():
    reply, _ = await call("/tz")
    assert runtime.get("timezone") in reply

    reply, save = await call("/tz Europe/Moscow")
    assert runtime.get("timezone") == "Europe/Moscow"
    save.assert_called_once_with("timezone", "Europe/Moscow")

    reply, save = await call("/tz Mars/Base")
    assert reply.startswith("❌")
    save.assert_not_called()


async def test_replies_follow_the_language_setting():
    runtime.set_value("language", "ru")
    reply, _ = await call("/mode")
    assert "Режим доставки" in reply
    assert i18n.get_language() == "ru"


async def test_stats_mentions_queued_stories_only_when_there_are_some():
    client = FakeClient()
    commands.register_commands(client, 2)
    handler, match = client.match("/stats")
    event = SimpleNamespace(pattern_match=match, reply=AsyncMock())
    with patch.object(commands.metrics, "get_stats_last_hours", return_value=(
            {"total": 10, "sent": 4, "queued": 3, "skipped": 3}, [{"reason": "published", "cnt": 4}])):
        await handler(event)
    text = event.reply.await_args.args[0]
    assert "Queued for digest: 3" in text and "Published: 4" in text

    event = SimpleNamespace(pattern_match=match, reply=AsyncMock())
    with patch.object(commands.metrics, "get_stats_last_hours", return_value=(
            {"total": 1, "sent": 1, "queued": 0, "skipped": 0}, [])):
        await handler(event)
    assert "Queued" not in event.reply.await_args.args[0]


async def test_menu_lists_the_new_commands_in_both_languages():
    client = FakeClient()
    commands.register_commands(client, 2)
    handler, match = client.match("/menu")
    for language, expected in (("en", "Delivery and filters"), ("ru", "Доставка и фильтры")):
        runtime.set_value("language", language)
        event = SimpleNamespace(pattern_match=match, respond=AsyncMock())
        await handler(event)
        text = event.respond.await_args.args[0]
        assert expected in text
        for command in ("/mode", "/digest", "/quiet", "/tz", "/mute", "/unmute", "/lang"):
            assert command in text, (language, command)

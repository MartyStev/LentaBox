import unittest
from datetime import datetime, timedelta, UTC
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import config
from handlers import maintenance

NOW = datetime(2026, 10, 11, 12, tzinfo=UTC)
CHANNEL = {"telegram_id": -10042, "username": "news", "title": "News"}


def cursor(last_message_id, hours_ago):
    return {"channel_id": "-10042", "last_message_id": last_message_id,
            "updated_at": NOW - timedelta(hours=hours_ago)}


class StallCheckTests(unittest.IsolatedAsyncioTestCase):
    async def run_check(self, cursor_row, latest):
        alerter = SimpleNamespace(notify=AsyncMock(return_value=True))
        fetch_latest = AsyncMock(return_value=latest)
        with patch.object(maintenance.channels, "list_channels", return_value=[CHANNEL]), \
             patch.object(maintenance.cursors, "list_all", return_value=[cursor_row]):
            stalled = await maintenance.stall_check_once(
                None, alerter, now=NOW, fetch_latest=fetch_latest,
            )
        return stalled, alerter, fetch_latest

    async def test_old_cursor_with_newer_old_messages_is_stalled(self):
        latest = SimpleNamespace(id=120, date=NOW - timedelta(hours=5))
        stalled, alerter, _ = await self.run_check(cursor(100, hours_ago=6), latest)
        self.assertEqual(stalled, ["-10042"])
        text = alerter.notify.await_args.args[1]
        self.assertIn("@news", text)
        self.assertIn("100", text)
        self.assertIn("120", text)

    async def test_quiet_channel_is_not_stalled(self):
        latest = SimpleNamespace(id=100, date=NOW - timedelta(hours=10))
        stalled, alerter, _ = await self.run_check(cursor(100, hours_ago=10), latest)
        self.assertEqual(stalled, [])
        alerter.notify.assert_not_awaited()

    async def test_recent_cursor_skips_telegram_call(self):
        stalled, _, fetch_latest = await self.run_check(cursor(100, hours_ago=1), None)
        self.assertEqual(stalled, [])
        fetch_latest.assert_not_awaited()

    async def test_fresh_messages_are_not_a_stall_yet(self):
        latest = SimpleNamespace(id=120, date=NOW - timedelta(minutes=10))
        stalled, _, _ = await self.run_check(cursor(100, hours_ago=6), latest)
        self.assertEqual(stalled, [])

    async def test_unreadable_channel_does_not_break_the_sweep(self):
        alerter = SimpleNamespace(notify=AsyncMock())
        fetch_latest = AsyncMock(side_effect=RuntimeError("no access"))
        with patch.object(maintenance.channels, "list_channels", return_value=[CHANNEL]), \
             patch.object(maintenance.cursors, "list_all", return_value=[cursor(100, 6)]), \
             patch.object(maintenance.log, "exception"):
            stalled = await maintenance.stall_check_once(None, alerter, now=NOW, fetch_latest=fetch_latest)
        self.assertEqual(stalled, [])


class ExpireClaimsTests(unittest.IsolatedAsyncioTestCase):
    async def test_expired_claims_are_reported_with_links(self):
        alerter = SimpleNamespace(notify=AsyncMock(return_value=True))
        row = {"id": 7, "cluster_id": 1, "channel_id": "-10042", "message_id": 55,
               "created_at": NOW, "username": "news", "title": "News"}
        with patch.object(maintenance.publications, "expire_pending", return_value=[row]) as expire:
            rows = await maintenance.expire_claims_once(alerter)
        expire.assert_called_once_with(config.CLAIM_EXPIRE_HOURS)
        self.assertEqual(rows, [row])
        text = alerter.notify.await_args.args[1]
        self.assertIn("#7", text)
        self.assertIn("https://t.me/news/55", text)

    async def test_nothing_to_expire_sends_no_alert(self):
        alerter = SimpleNamespace(notify=AsyncMock())
        with patch.object(maintenance.publications, "expire_pending", return_value=[]):
            await maintenance.expire_claims_once(alerter)
        alerter.notify.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()

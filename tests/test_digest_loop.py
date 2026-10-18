"""Sending the digest: when it is due, how it is sent and what happens on failure."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

import config
from core import runtime
from handlers import maintenance

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
ROWS = [
    {"id": 1, "headline": "Первая", "link": "https://t.me/news/1", "channel_label": "@news"},
    {"id": 2, "headline": "Вторая", "link": "https://t.me/news/2", "channel_label": "@news"},
]


@pytest.fixture(autouse=True)
def reset_settings(monkeypatch):
    monkeypatch.setattr(config, "DIGEST_PART_PAUSE_SEC", 0)
    yield
    for name in ("delivery_mode", "digest_hours", "quiet_hours", "timezone"):
        runtime.reset(name)


class World:
    """A fake client, a fake digest table and an alerter, patched into the maintenance module."""

    def __init__(self, rows=ROWS, last_sent=None):
        self.client = SimpleNamespace(send_message=AsyncMock())
        self.alerter = SimpleNamespace(notify=AsyncMock(return_value=True))
        self.rows = list(rows)
        self.last_sent = last_sent
        self.marked = []

    def __enter__(self):
        self.patches = [
            patch.object(maintenance.digest_db, "count_unsent", side_effect=lambda: len(self.rows)),
            patch.object(maintenance.digest_db, "list_unsent", side_effect=lambda limit=300: self.rows[:limit]),
            patch.object(maintenance.digest_db, "last_sent_at", side_effect=lambda: self.last_sent),
            patch.object(maintenance.digest_db, "mark_sent", side_effect=self._mark),
        ]
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self.patches:
            p.stop()

    def _mark(self, ids):
        self.marked.extend(ids)
        return len(ids)

    async def run(self, **kwargs):
        return await maintenance.digest_once(self.client, self.alerter, now=NOW, **kwargs)


async def test_instant_mode_outside_quiet_hours_flushes_leftovers_at_once():
    with World() as w:
        assert await w.run() == 2
    w.client.send_message.assert_awaited_once()
    args, kwargs = w.client.send_message.await_args
    assert args[0] == config.target_chat_id
    assert "Первая" in args[1] and "Вторая" in args[1]
    assert kwargs == {"parse_mode": "html", "link_preview": False}
    assert w.marked == [1, 2]


async def test_nothing_is_sent_when_the_queue_is_empty():
    with World(rows=[]) as w:
        assert await w.run() == 0
    w.client.send_message.assert_not_awaited()


async def test_quiet_hours_hold_the_digest_back():
    runtime.set_value("quiet_hours", "10:00-14:00")
    with World() as w:
        assert await w.run() == 0
    w.client.send_message.assert_not_awaited()
    assert w.marked == []


async def test_digest_mode_waits_for_the_period_to_pass():
    runtime.set_value("delivery_mode", "digest")
    runtime.set_value("digest_hours", "3")
    with World(last_sent=NOW - timedelta(hours=1)) as w:
        assert await w.run() == 0
    with World(last_sent=NOW - timedelta(hours=3, minutes=1)) as w:
        assert await w.run() == 2
    with World(last_sent=None) as w:
        assert await w.run() == 2


async def test_force_ignores_period_and_quiet_hours():
    runtime.set_value("delivery_mode", "digest")
    runtime.set_value("quiet_hours", "10:00-14:00")
    with World(last_sent=NOW - timedelta(minutes=1)) as w:
        assert await w.run(force=True) == 2


async def test_failed_send_keeps_rows_queued_and_alerts_the_owner():
    with World() as w:
        w.client.send_message.side_effect = ConnectionError("lost")
        assert await w.run() == 0
    assert w.marked == []
    w.alerter.notify.assert_awaited_once()
    assert w.alerter.notify.await_args.args[0] == "digest_failed"


async def test_a_long_digest_is_sent_in_parts_and_marked_once_at_the_end():
    many = [{"id": i, "headline": f"Новость {i} " + "x" * 90, "link": f"https://t.me/news/{i}",
             "channel_label": "@news"} for i in range(1, 121)]
    with World(rows=many) as w:
        assert await w.run() == 120
    assert w.client.send_message.await_count > 1
    assert w.marked == list(range(1, 121))


async def test_part_failure_marks_nothing_so_the_whole_digest_is_retried():
    many = [{"id": i, "headline": f"Новость {i} " + "x" * 90, "link": None, "channel_label": "@n"}
            for i in range(1, 121)]
    with World(rows=many) as w:
        w.client.send_message.side_effect = [None, ConnectionError("lost")]
        assert await w.run() == 0
    assert w.marked == []


async def test_digest_loop_runs_until_cancelled_and_survives_errors(monkeypatch):
    calls = []

    async def fake_once(client, alerter, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")
        return 0

    monkeypatch.setattr(maintenance, "digest_once", fake_once)
    monkeypatch.setattr(config, "DIGEST_CHECK_SEC", 0.01)
    import asyncio
    task = asyncio.create_task(maintenance.digest_loop(SimpleNamespace(), SimpleNamespace()))
    await asyncio.sleep(0.08)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(calls) >= 2


async def test_purge_loop_also_removes_old_sent_digest_rows(monkeypatch):
    monkeypatch.setattr(maintenance.metrics, "purge_old_decisions", lambda days: 0)
    purged = []
    monkeypatch.setattr(maintenance.digest_db, "purge_sent", lambda days: purged.append(days) or 0)
    import asyncio

    async def stop(_):
        raise asyncio.CancelledError

    monkeypatch.setattr(maintenance.asyncio, "sleep", stop)
    with pytest.raises(asyncio.CancelledError):
        await maintenance.purge_loop()
    assert purged == [config.DIGEST_RETENTION_DAYS]

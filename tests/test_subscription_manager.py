import unittest
from datetime import datetime, timedelta, UTC
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from core import runtime
from core import subscriptions as subs
from handlers import maintenance
from handlers import subscriptions as handler


def sub(telegram_id, title, username=None):
    return subs.Sub(telegram_id=telegram_id, username=username, title=title)


SUBS = [sub(1, "Alpha", "alpha"), sub(2, "Beta"), sub(3, "Gamma", "gamma")]
FOLDERS = {"Новости": {"include": {1, 2}, "exclude": set(), "broadcasts": False}}


class ManagerTests(unittest.IsolatedAsyncioTestCase):
    def make(self, tracked=()):
        self.rows = [{"telegram_id": t, "source": "manual", "title": str(t)} for t in tracked]
        patches = [
            patch.object(handler.channels, "list_channels", side_effect=lambda: list(self.rows)),
            patch.object(handler.channels, "list_exclusions", return_value=set()),
        ]
        self.add = MagicMock()
        self.remove = MagicMock()
        self.add_exclusion = MagicMock()
        self.clear_exclusion = MagicMock()
        patches += [
            patch.object(handler.channels, "add_channel", self.add),
            patch.object(handler.channels, "remove_channel", self.remove),
            patch.object(handler.channels, "add_exclusion", self.add_exclusion),
            patch.object(handler.channels, "clear_exclusion", self.clear_exclusion),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.changed = AsyncMock()
        return handler.SubscriptionManager(
            AsyncMock(return_value=SUBS), AsyncMock(return_value=FOLDERS), self.changed,
        )

    async def test_show_marks_tracked_and_numbers_items(self):
        manager = self.make(tracked=[2])
        text = await manager.show("")
        self.assertIn("1. ⬜ @alpha", text)
        self.assertIn("2. ✅ Beta", text)
        self.assertIn("подключено 1", text)

    async def test_show_filter_new_and_page_error(self):
        manager = self.make(tracked=[2])
        text = await manager.show("new")
        self.assertNotIn("Beta", text)
        self.assertIn("2. ⬜ @gamma", text)
        with self.assertRaisesRegex(ValueError, "Страницы 5 нет"):
            await manager.show("page 5")

    async def test_track_by_numbers_uses_last_listing_and_marks_sync_source(self):
        manager = self.make(tracked=[2])
        await manager.show("new")  # listing: Alpha, Gamma
        reply = await manager.track("2")
        self.add.assert_called_once_with(3, "gamma", "Gamma", "sync")
        self.clear_exclusion.assert_called_once_with(3)
        self.changed.assert_awaited_once_with(force=True)
        self.assertIn("@gamma", reply)

    async def test_track_numbers_without_listing_explains_what_to_do(self):
        manager = self.make()
        with self.assertRaisesRegex(ValueError, "/subs"):
            await manager.track("1")

    async def test_track_all_and_skip_already_tracked(self):
        manager = self.make(tracked=[1])
        await manager.track("all")
        self.assertEqual([c.args[0] for c in self.add.call_args_list], [2, 3])

    async def test_track_folder(self):
        manager = self.make(tracked=[1])
        reply = await manager.track("folder новости")
        self.add.assert_called_once_with(2, None, "Beta", "sync")
        self.assertIn("папка «Новости»", reply)

    async def test_unknown_folder_lists_known_ones(self):
        manager = self.make()
        with self.assertRaisesRegex(ValueError, "Новости"):
            await manager.track("folder Спорт")

    async def test_untrack_excludes_channels_from_autosync(self):
        manager = self.make(tracked=[1, 2])
        await manager.show("")
        await manager.untrack("1-2")
        self.assertEqual([c.args[0] for c in self.remove.call_args_list], [1, 2])
        self.assertEqual([c.args[0] for c in self.add_exclusion.call_args_list], [1, 2])

    async def test_sync_preview_and_apply(self):
        manager = self.make(tracked=[1])
        self.rows.append({"telegram_id": 9, "source": "sync", "title": "Gone"})
        preview = await manager.sync("")
        self.assertIn("Новые подписки: 2", preview)
        self.assertIn("Отписались: 1", preview)
        self.add.assert_not_called()
        await manager.sync("apply")
        self.assertEqual({c.args[0] for c in self.add.call_args_list}, {2, 3})
        self.remove.assert_called_once_with(9)

    async def test_folders_summary(self):
        manager = self.make(tracked=[1])
        text = await manager.folders()
        self.assertIn("Новости: каналов 2, не подключено 1", text)

    async def test_autosync_toggle_persists_and_syncs(self):
        manager = self.make()
        self.addCleanup(runtime.reset, "autosync")
        with patch.object(handler.settings_db, "save") as save:
            reply = await manager.autosync("on")
        save.assert_called_once_with("autosync", "on")
        self.assertTrue(runtime.get("autosync"))
        self.assertIn("Автосинхронизация включена", reply)
        self.assertEqual(self.add.call_count, 3)


class MaintenanceTests(unittest.IsolatedAsyncioTestCase):
    async def test_autosync_does_nothing_when_disabled(self):
        runtime.reset("autosync")
        manager = SimpleNamespace(_fetch_subs=AsyncMock(), _changed=AsyncMock())
        self.assertFalse(await maintenance.autosync_once(manager))
        manager._fetch_subs.assert_not_awaited()

    async def test_silence_alert_after_threshold(self):
        alerter = SimpleNamespace(notify=AsyncMock(return_value=True))
        now = datetime(2026, 10, 11, 12, tzinfo=UTC)
        with patch.object(maintenance.channels, "list_channels", return_value=[{"telegram_id": 1}]), \
             patch.object(maintenance.posts, "last_saved_at", return_value=now - timedelta(hours=7)):
            self.assertTrue(await maintenance.silence_check_once(alerter, now=now))
        self.assertIn("7 ч", alerter.notify.await_args.args[1])

    async def test_no_silence_alert_for_recent_post_or_no_channels(self):
        alerter = SimpleNamespace(notify=AsyncMock())
        now = datetime(2026, 10, 11, 12, tzinfo=UTC)
        with patch.object(maintenance.channels, "list_channels", return_value=[{"telegram_id": 1}]), \
             patch.object(maintenance.posts, "last_saved_at", return_value=now - timedelta(hours=1)):
            self.assertFalse(await maintenance.silence_check_once(alerter, now=now))
        with patch.object(maintenance.channels, "list_channels", return_value=[]):
            self.assertFalse(await maintenance.silence_check_once(alerter, now=now))
        alerter.notify.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()

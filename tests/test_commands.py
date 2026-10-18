import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from handlers import commands


class FakeClient:
    def __init__(self):
        self.handlers = []
        self.get_entity = AsyncMock(
            return_value=SimpleNamespace(username="news", title="News", broadcast=True),
        )

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


class CommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_add_accepts_tab_separator(self):
        client = FakeClient()
        refresh = AsyncMock()
        commands.register_commands(client, 2, on_channels_changed=refresh)
        handler, match = client.match("/add\t@news")
        event = SimpleNamespace(pattern_match=match, reply=AsyncMock())
        with patch.object(commands, "get_peer_id", return_value=-10042), \
             patch.object(commands.channels, "clear_exclusion"), \
             patch.object(commands.channels, "add_channel") as add:
            await handler(event)
        add.assert_called_once_with(-10042, "news", "News")
        client.get_entity.assert_awaited_once_with("news")
        refresh.assert_awaited_once_with(force=True)

    async def _run_add(self, text, entity=None):
        client = FakeClient()
        if entity is not None:
            client.get_entity = AsyncMock(return_value=entity)
        commands.register_commands(client, 2, on_channels_changed=AsyncMock())
        handler, match = client.match(text)
        event = SimpleNamespace(pattern_match=match, reply=AsyncMock())
        with patch.object(commands, "get_peer_id", return_value=-10042), \
             patch.object(commands.channels, "clear_exclusion"), \
             patch.object(commands.channels, "add_channel") as add:
            await handler(event)
        return client, event, add

    async def test_add_rejects_text_that_is_not_a_channel_reference(self):
        client, event, add = await self._run_add("/add hello world")
        client.get_entity.assert_not_awaited()
        add.assert_not_called()
        self.assertIn("❌", event.reply.await_args.args[0])

    async def test_add_explains_that_invite_links_are_not_supported(self):
        client, event, add = await self._run_add("/add https://t.me/+AbCdEfGh1234")
        client.get_entity.assert_not_awaited()
        add.assert_not_called()
        self.assertIn("/subs", event.reply.await_args.args[0])

    async def test_add_rejects_users_groups_and_bots(self):
        user = SimpleNamespace(username="some_bot", title=None, broadcast=False)
        _, event, add = await self._run_add("/add @some_bot", entity=user)
        add.assert_not_called()
        self.assertIn("❌", event.reply.await_args.args[0])

    async def test_pending_page_shows_source_link(self):
        client = FakeClient()
        commands.register_commands(client, 2)
        handler, match = client.match("/pending page 2")
        event = SimpleNamespace(pattern_match=match, reply=AsyncMock())
        row = {
            "id": 7, "cluster_id": 9, "channel_id": "-10042",
            "message_id": 12, "created_at": "today", "username": "news", "title": "News",
        }
        with patch.object(commands.publications, "list_pending", return_value=[row]) as pending:
            await handler(event)
        pending.assert_called_once_with(11, 10)
        self.assertIn("https://t.me/news/12", event.reply.await_args.args[0])

    async def test_why_accepts_post_link_and_shows_excerpt(self):
        client = FakeClient()
        commands.register_commands(client, 2)
        handler, match = client.match("/why https://t.me/news/321")
        event = SimpleNamespace(pattern_match=match, reply=AsyncMock())
        row = {"created_at": "now", "channel_id": "-1", "decision": "skip",
               "reason": "advertisement", "cluster_id": None, "fuzzy_score": None,
               "cluster_score": None, "excerpt": "Скидки и erid"}
        with patch.object(commands.metrics, "get_why_by_message_id", return_value=[row]) as why:
            await handler(event)
        why.assert_called_once_with(321, 5)
        self.assertIn("Скидки и erid", event.reply.await_args.args[0])

    async def test_threshold_changes_and_validates(self):
        client = FakeClient()
        commands.register_commands(client, 2)
        self.addCleanup(commands.runtime.reset, "cluster_threshold")
        handler, match = client.match("/threshold cluster 0.9")
        event = SimpleNamespace(pattern_match=match, reply=AsyncMock())
        with patch.object(commands.settings_db, "save") as save:
            await handler(event)
        save.assert_called_once_with("cluster_threshold", 0.9)
        self.assertEqual(commands.runtime.get("cluster_threshold"), 0.9)

        handler, match = client.match("/threshold cluster 5")
        event = SimpleNamespace(pattern_match=match, reply=AsyncMock())
        await handler(event)
        self.assertTrue(event.reply.await_args.args[0].startswith("❌"))

    async def test_lang_switches_the_language_and_persists_it(self):
        client = FakeClient()
        commands.register_commands(client, 2)
        self.addCleanup(commands.runtime.reset, "language")
        handler, match = client.match("/lang en")
        event = SimpleNamespace(pattern_match=match, reply=AsyncMock())
        with patch.object(commands.settings_db, "save") as save:
            await handler(event)
        save.assert_called_once_with("language", "en")
        self.assertEqual(commands.i18n.get_language(), "en")
        self.assertIn("Message language: en", event.reply.await_args.args[0])

    async def test_lang_without_argument_shows_usage_and_rejects_unknown(self):
        client = FakeClient()
        commands.register_commands(client, 2)
        self.addCleanup(commands.runtime.reset, "language")
        handler, match = client.match("/lang")
        event = SimpleNamespace(pattern_match=match, reply=AsyncMock())
        await handler(event)
        self.assertIn("/lang ru|en", event.reply.await_args.args[0])

        handler, match = client.match("/lang de")
        event = SimpleNamespace(pattern_match=match, reply=AsyncMock())
        with patch.object(commands.settings_db, "save") as save:
            await handler(event)
        save.assert_not_called()
        self.assertTrue(event.reply.await_args.args[0].startswith("❌"))

    async def _mute(self, text, **patches):
        client = FakeClient()
        refresh = AsyncMock()
        commands.register_commands(client, 2, on_channels_changed=refresh)
        handler, match = client.match(text)
        event = SimpleNamespace(pattern_match=match, reply=AsyncMock())
        with patch.object(commands.mute_words, "add", return_value=patches.get("add", "added")) as add, \
             patch.object(commands.mute_words, "remove", return_value=patches.get("remove", True)) as remove, \
             patch.object(commands.mute_words, "list_words", return_value=patches.get("words", [])) as words:
            await handler(event)
        return event.reply.await_args.args[0], add, remove, words, refresh

    async def test_mute_adds_a_word_and_refreshes_the_listener(self):
        reply, add, _, _, refresh = await self._mute("/mute Курс доллара")
        add.assert_called_once_with("Курс доллара")
        refresh.assert_awaited_once_with(force=True)
        self.assertTrue(reply.startswith("✅"))

    async def test_mute_without_argument_lists_words(self):
        reply, add, _, words, _ = await self._mute("/mute", words=["доллар", "футбол"])
        add.assert_not_called()
        self.assertIn("доллар", reply)
        self.assertIn("футбол", reply)

    async def test_mute_reports_duplicates_limits_and_invalid_words(self):
        for outcome in ("exists", "limit", "invalid"):
            reply, _, _, _, refresh = await self._mute("/mute слово", add=outcome)
            self.assertTrue(reply.startswith("❌") or reply.startswith("ℹ"), (outcome, reply))
            refresh.assert_not_awaited()

    async def test_unmute_removes_a_word(self):
        reply, _, remove, _, refresh = await self._mute("/unmute Доллар")
        remove.assert_called_once_with("Доллар")
        refresh.assert_awaited_once_with(force=True)
        reply, _, _, _, refresh = await self._mute("/unmute нет", remove=False)
        self.assertTrue(reply.startswith("❌"))
        refresh.assert_not_awaited()

    async def test_remove_excludes_channel_from_autosync(self):
        client = FakeClient()
        commands.register_commands(client, 2)
        handler, match = client.match("/remove @news")
        event = SimpleNamespace(pattern_match=match, reply=AsyncMock())
        with patch.object(commands, "get_peer_id", return_value=-10042), \
             patch.object(commands.channels, "remove_channel") as remove, \
             patch.object(commands.channels, "add_exclusion") as exclude:
            await handler(event)
        remove.assert_called_once_with(-10042)
        exclude.assert_called_once_with(-10042)

    async def resolve(self, text, result=True):
        client = FakeClient()
        commands.register_commands(client, 2)
        handler, match = client.match(text)
        event = SimpleNamespace(pattern_match=match, reply=AsyncMock())
        with patch.object(commands.publications, "resolve_pending", return_value=result) as resolve:
            await handler(event)
        return resolve, event.reply.await_args.args[0]

    async def test_pending_resolve_sent(self):
        resolve, reply = await self.resolve("/pending resolve 7 sent")
        resolve.assert_called_once_with(7, "sent")
        self.assertIn("повтора не будет", reply)

    async def test_pending_resolve_failed_schedules_retry(self):
        resolve, reply = await self.resolve("/pending resolve 7 failed")
        resolve.assert_called_once_with(7, "failed")
        self.assertIn("будет повторена", reply)

    async def test_pending_resolve_unknown_claim(self):
        _, reply = await self.resolve("/pending resolve 7 sent", result=False)
        self.assertIn("не найден", reply)

    async def test_pending_resolve_validates_arguments(self):
        for text in ("/pending resolve", "/pending resolve 7", "/pending resolve x sent",
                     "/pending resolve 7 maybe"):
            resolve, reply = await self.resolve(text)
            resolve.assert_not_called()
            self.assertIn("Использование", reply)


if __name__ == "__main__":
    unittest.main()

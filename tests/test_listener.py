import asyncio
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from telethon import events
from telethon.extensions import html as telegram_html
from telethon.tl.types import MessageMediaPhoto

import config
from handlers import listener

config.SEND_MIN_INTERVAL_SEC = 0


PHOTOS = {n: MessageMediaPhoto() for n in (1, 2, 3)}


class FakeClient:
    def __init__(self):
        self.handlers = {}
        self.send_file = AsyncMock()
        self.send_message = AsyncMock()

    def on(self, builder):
        def register(handler):
            self.handlers[builder if isinstance(builder, type) else type(builder)] = handler
            return handler
        return register


class ListenerTests(unittest.IsolatedAsyncioTestCase):
    def test_content_escapes_html_and_respects_limits(self):
        footer = listener.build_footer(
            {"telegram_id": -10042, "username": None, "title": "A < B"}, 7,
        )
        self.assertIn("A &lt; B", footer)
        self.assertIn("https://t.me/c/42/7", footer)
        content = listener.build_content("<b>&" * 1000, footer, 900)
        plain, _ = telegram_html.parse(content)
        self.assertLessEqual(len(plain), 900)
        self.assertIn("<b>&", plain)
        self.assertIn("Текст сокращён", plain)
        emoji_content = listener.build_content("😀" * 1000, footer, 900)
        emoji_plain, _ = telegram_html.parse(emoji_content)
        self.assertLessEqual(len(emoji_plain.encode("utf-16-le")) // 2, 900)

    def test_rich_html_is_used_when_it_fits(self):
        footer = listener.build_footer({"telegram_id": -10042, "username": "news", "title": "News"}, 7)
        rich = "<b>Заголовок</b> и <i>текст</i>"
        content = listener.build_content("Заголовок и текст", footer, 900, rich_html=rich)
        self.assertTrue(content.startswith(rich))
        self.assertTrue(content.endswith(footer.strip()))

    def test_rich_html_falls_back_to_plain_text_when_too_long(self):
        footer = listener.build_footer({"telegram_id": -10042, "username": "news", "title": "News"}, 7)
        plain = "слово " * 400
        rich = "<b>" + plain + "</b>"
        content = listener.build_content(plain, footer, 900, rich_html=rich)
        self.assertNotIn("<b>слово", content)
        text, _ = telegram_html.parse(content)
        self.assertLessEqual(len(text), 900)
        self.assertIn("Текст сокращён", text)

    def test_missing_rich_html_keeps_escaping_behaviour(self):
        footer = listener.build_footer({"telegram_id": -10042, "username": "news", "title": "News"}, 7)
        content = listener.build_content("a < b", footer, 900, rich_html=None)
        self.assertIn("a &lt; b", content)

    async def test_album_caption_on_later_item_is_sent_once(self):
        client = FakeClient()
        channel = {"telegram_id": -10042, "username": "news", "title": "News"}
        with ExitStack() as patches:
            patches.enter_context(patch.object(listener.channels, "list_channels", return_value=[channel]))
            patches.enter_context(patch.object(listener.mute_words, "list_words", return_value=[]))
            patches.enter_context(patch.object(listener.posts, "post_exists", return_value=False))
            patches.enter_context(patch.object(listener.posts, "origin_seen", return_value=False))
            patches.enter_context(patch.object(listener.posts, "get_recent_texts", return_value=[]))
            patches.enter_context(patch.object(listener.clusters, "get_recent_clusters", return_value=[]))
            patches.enter_context(patch.object(listener.clusters, "create_cluster", return_value=11))
            claim = patches.enter_context(patch.object(listener.publications, "claim", side_effect=[5, None]))
            patches.enter_context(patch.object(listener.publications, "has_pending_conflict", return_value=False))
            finalize = patches.enter_context(patch.object(listener.publications, "finalize"))
            patches.enter_context(patch.object(listener.metrics, "log_decision"))
            patches.enter_context(patch.object(listener, "embed", new=AsyncMock(return_value=[1.0, 0.0])))
            patches.enter_context(patch.object(listener, "get_peer_id", return_value=-10042))

            listener.register_listener(client)
            messages = [
                SimpleNamespace(id=100, grouped_id=1, message="", media=PHOTOS[1]),
                SimpleNamespace(id=101, grouped_id=1,
                                message="Новость <важная> с подробностями", media=PHOTOS[2]),
            ]
            event = SimpleNamespace(messages=messages, get_chat=AsyncMock(return_value=object()))

            # Album events arrive after individual NewMessage events.
            for message in messages:
                await client.handlers[events.NewMessage](SimpleNamespace(message=message))
            await client.handlers[events.Album](event)
            await client.handlers[events.Album](event)

            client.send_file.assert_awaited_once()
            self.assertEqual(client.send_file.await_args.args[1], [PHOTOS[1], PHOTOS[2]])
            self.assertIn("&lt;важная&gt;", client.send_file.await_args.kwargs["caption"])
            finalize.assert_called_once()
            self.assertEqual(claim.call_count, 2)

    async def test_simultaneous_messages_publish_only_one(self):
        client = FakeClient()
        channel = {"telegram_id": -10042, "username": "news", "title": "News"}
        with ExitStack() as patches:
            patches.enter_context(patch.object(listener.channels, "list_channels", return_value=[channel]))
            patches.enter_context(patch.object(listener.mute_words, "list_words", return_value=[]))
            patches.enter_context(patch.object(listener.posts, "post_exists", return_value=False))
            patches.enter_context(patch.object(listener.posts, "origin_seen", return_value=False))
            patches.enter_context(patch.object(listener.posts, "get_recent_texts", return_value=[]))
            patches.enter_context(patch.object(listener.clusters, "get_recent_clusters", return_value=[]))
            patches.enter_context(patch.object(listener.clusters, "create_cluster", return_value=11))
            patches.enter_context(patch.object(listener.publications, "claim", side_effect=[5, None]))
            patches.enter_context(patch.object(listener.publications, "has_pending_conflict", return_value=False))
            patches.enter_context(patch.object(listener.publications, "finalize"))
            patches.enter_context(patch.object(listener.metrics, "log_decision"))
            patches.enter_context(patch.object(listener, "embed", new=AsyncMock(return_value=[1.0, 0.0])))
            patches.enter_context(patch.object(listener, "get_peer_id", return_value=-10042))

            listener.register_listener(client)
            def make_event(message_id):
                return SimpleNamespace(
                    message=SimpleNamespace(id=message_id, grouped_id=None,
                                            message="Достаточно длинная новость для проверки", media=None),
                    get_chat=AsyncMock(return_value=object()),
                )
            await asyncio.gather(
                client.handlers[events.NewMessage](make_event(1)),
                client.handlers[events.NewMessage](make_event(2)),
            )
            client.send_message.assert_awaited_once()

    async def test_unknown_send_result_keeps_claim_pending(self):
        client = FakeClient()
        client.send_message.side_effect = TimeoutError("connection lost")
        channel = {"telegram_id": -10042, "username": "news", "title": "News"}
        with ExitStack() as patches:
            patches.enter_context(patch.object(listener.channels, "list_channels", return_value=[channel]))
            patches.enter_context(patch.object(listener.mute_words, "list_words", return_value=[]))
            patches.enter_context(patch.object(listener.posts, "post_exists", return_value=False))
            patches.enter_context(patch.object(listener.posts, "origin_seen", return_value=False))
            patches.enter_context(patch.object(listener.posts, "get_recent_texts", return_value=[]))
            patches.enter_context(patch.object(listener.clusters, "get_recent_clusters", return_value=[]))
            patches.enter_context(patch.object(listener.clusters, "create_cluster", return_value=11))
            patches.enter_context(patch.object(listener.publications, "claim", return_value=5))
            finalize = patches.enter_context(patch.object(listener.publications, "finalize"))
            patches.enter_context(patch.object(listener.metrics, "log_decision"))
            patches.enter_context(patch.object(listener, "embed", new=AsyncMock(return_value=[1.0, 0.0])))
            patches.enter_context(patch.object(listener, "get_peer_id", return_value=-10042))
            patches.enter_context(patch.object(listener.log, "exception"))

            listener.register_listener(client)
            event = SimpleNamespace(
                message=SimpleNamespace(id=1, grouped_id=None,
                                        message="Достаточно длинная новость для проверки", media=None),
                get_chat=AsyncMock(return_value=object()),
            )
            await client.handlers[events.NewMessage](event)
            finalize.assert_not_called()

    async def test_backfill_groups_album_and_advances_cursor(self):
        client = FakeClient()
        client.get_entity = AsyncMock(return_value=object())
        channel = {"telegram_id": -10042, "username": "news", "title": "News"}
        messages = [
            SimpleNamespace(id=11, grouped_id=9, message="", media=PHOTOS[1]),
            SimpleNamespace(id=12, grouped_id=9,
                            message="Достаточно длинная подпись к альбому", media=PHOTOS[2]),
            SimpleNamespace(id=13, grouped_id=None, message="", media=PHOTOS[3]),
        ]

        async def iter_messages(entity, **kwargs):
            self.assertEqual(kwargs, {"min_id": 10, "reverse": True})
            for message in messages:
                yield message

        client.iter_messages = iter_messages
        with ExitStack() as patches:
            patches.enter_context(patch.object(listener.channels, "list_channels", return_value=[channel]))
            patches.enter_context(patch.object(listener.mute_words, "list_words", return_value=[]))
            patches.enter_context(patch.object(listener.cursors, "get", return_value=10))
            advance = patches.enter_context(patch.object(listener.cursors, "advance"))
            patches.enter_context(patch.object(listener.posts, "post_exists", return_value=False))
            patches.enter_context(patch.object(listener.posts, "origin_seen", return_value=False))
            patches.enter_context(patch.object(listener.posts, "get_recent_texts", return_value=[]))
            patches.enter_context(patch.object(listener.clusters, "get_recent_clusters", return_value=[]))
            patches.enter_context(patch.object(listener.clusters, "create_cluster", return_value=11))
            patches.enter_context(patch.object(listener.publications, "claim", return_value=5))
            patches.enter_context(patch.object(listener.publications, "finalize"))
            patches.enter_context(patch.object(listener.metrics, "log_decision"))
            patches.enter_context(patch.object(listener, "embed", new=AsyncMock(return_value=[1.0, 0.0])))

            _, catch_up_once, _ = listener.register_listener(client)
            await catch_up_once()
            self.assertEqual([call.args[1] for call in advance.call_args_list], [12, 13])
            client.send_file.assert_awaited_once()

    async def test_backfill_keeps_cursor_before_failed_message(self):
        client = FakeClient()
        client.get_entity = AsyncMock(return_value=object())
        channel = {"telegram_id": -10042, "username": "news", "title": "News"}

        async def iter_messages(entity, **kwargs):
            yield SimpleNamespace(id=11, grouped_id=None,
                                  message="Достаточно длинная новость для проверки", media=None)

        client.iter_messages = iter_messages
        with ExitStack() as patches:
            patches.enter_context(patch.object(listener.channels, "list_channels", return_value=[channel]))
            patches.enter_context(patch.object(listener.mute_words, "list_words", return_value=[]))
            patches.enter_context(patch.object(listener.cursors, "get", return_value=10))
            advance = patches.enter_context(patch.object(listener.cursors, "advance"))
            patches.enter_context(patch.object(listener.posts, "post_exists", return_value=False))
            patches.enter_context(patch.object(listener.posts, "origin_seen", return_value=False))
            patches.enter_context(patch.object(listener.posts, "get_recent_texts", return_value=[]))
            patches.enter_context(patch.object(listener.metrics, "log_decision"))
            patches.enter_context(patch.object(listener, "embed", new=AsyncMock(side_effect=RuntimeError("offline"))))
            patches.enter_context(patch.object(listener.log, "exception"))

            _, catch_up_once, _ = listener.register_listener(client)
            await catch_up_once()
            advance.assert_not_called()

    async def test_backfill_waits_for_pending_claim(self):
        client = FakeClient()
        client.get_entity = AsyncMock(return_value=object())
        channel = {"telegram_id": -10042, "username": "news", "title": "News"}

        async def iter_messages(entity, **kwargs):
            yield SimpleNamespace(id=11, grouped_id=None,
                                  message="Достаточно длинная новость для проверки", media=None)

        client.iter_messages = iter_messages
        with ExitStack() as patches:
            patches.enter_context(patch.object(listener.channels, "list_channels", return_value=[channel]))
            patches.enter_context(patch.object(listener.mute_words, "list_words", return_value=[]))
            patches.enter_context(patch.object(listener.cursors, "get", return_value=10))
            advance = patches.enter_context(patch.object(listener.cursors, "advance"))
            patches.enter_context(patch.object(listener.posts, "post_exists", return_value=False))
            patches.enter_context(patch.object(listener.posts, "origin_seen", return_value=False))
            patches.enter_context(patch.object(listener.posts, "get_recent_texts", return_value=[]))
            patches.enter_context(patch.object(listener.clusters, "get_recent_clusters", return_value=[]))
            patches.enter_context(patch.object(listener.clusters, "create_cluster", return_value=11))
            patches.enter_context(patch.object(listener.publications, "claim", return_value=None))
            patches.enter_context(patch.object(listener.publications, "has_pending_conflict", return_value=True))
            patches.enter_context(patch.object(listener.metrics, "log_decision"))
            patches.enter_context(patch.object(listener, "embed", new=AsyncMock(return_value=[1.0, 0.0])))

            _, catch_up_once, _ = listener.register_listener(client)
            await catch_up_once()
            advance.assert_not_called()


if __name__ == "__main__":
    unittest.main()

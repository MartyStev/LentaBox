import unittest
from datetime import datetime, timedelta, UTC
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from telethon import events
from telethon.errors import ChatForwardsRestrictedError, ChatWriteForbiddenError
from telethon.tl.types import MessageMediaPhoto

import config
from handlers import listener

CHANNEL = {"telegram_id": -10042, "username": "news", "title": "News"}
TEXT = "Достаточно длинная новость для проверки конвейера"


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


def event_for(text=TEXT, message_id=1, fwd_from=None, date=None):
    return SimpleNamespace(
        message=SimpleNamespace(id=message_id, grouped_id=None, message=text,
                                media=None, fwd_from=fwd_from, date=date),
        get_chat=AsyncMock(return_value=object()),
    )


class Pipeline:
    """Shared DB and Telegram stubs for testing the processing pipeline."""

    def __init__(self, test, embedding=(1.0, 0.0), clusters_rows=(), origin_seen=False, muted=()):
        self.client = FakeClient()
        stack = ExitStack()
        test.addCleanup(stack.close)
        def patch_obj(target, name, **kw):
            return stack.enter_context(patch.object(target, name, **kw))

        patch_obj(listener.channels, "list_channels", return_value=[CHANNEL])
        self.mute_words = patch_obj(listener.mute_words, "list_words", return_value=list(muted))
        patch_obj(listener.posts, "post_exists", return_value=False)
        patch_obj(listener.posts, "origin_seen", return_value=origin_seen)
        patch_obj(listener.posts, "get_recent_texts", return_value=[])
        patch_obj(listener.clusters, "get_recent_clusters", return_value=list(clusters_rows))
        self.create_cluster = patch_obj(listener.clusters, "create_cluster", return_value=99)
        self.update_centroid = patch_obj(listener.clusters, "update_centroid")
        self.claim = patch_obj(listener.publications, "claim", return_value=5)
        patch_obj(listener.publications, "has_pending_conflict", return_value=False)
        self.finalize = patch_obj(listener.publications, "finalize")
        self.release = patch_obj(listener.publications, "release")
        self.log_decision = patch_obj(listener.metrics, "log_decision")
        self.embed = patch_obj(listener, "embed", new=AsyncMock(return_value=list(embedding)))
        patch_obj(listener, "get_peer_id", return_value=-10042)
        patch_obj(listener.log, "exception")
        patch_obj(config, "SEND_MIN_INTERVAL_SEC", new=0)
        listener.register_listener(self.client)

    async def send(self, **kwargs):
        await self.client.handlers[events.NewMessage](event_for(**kwargs))

    def reasons(self):
        return [call.args[3] for call in self.log_decision.call_args_list]


class PipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_advertisement_is_skipped_with_excerpt(self):
        pipe = Pipeline(self)
        await pipe.send(text=TEXT + " erid: 2Vtzqx")
        pipe.client.send_message.assert_not_awaited()
        self.assertEqual(pipe.reasons(), ["advertisement"])
        self.assertIn("erid", pipe.log_decision.call_args.args[7])

    async def test_digest_mode_queues_the_story_instead_of_sending_it(self):
        pipe = Pipeline(self)
        self.addCleanup(listener.runtime.reset, "delivery_mode")
        listener.runtime.set_value("delivery_mode", "digest")
        await pipe.send(text="Заголовок новости\nПодробности для проверки очереди")
        pipe.client.send_message.assert_not_awaited()
        pipe.client.send_file.assert_not_awaited()
        pipe.finalize.assert_called_once()
        entry = pipe.finalize.call_args.kwargs["queue_entry"]
        self.assertEqual(entry["headline"], "Заголовок новости")
        self.assertEqual(entry["link"], "https://t.me/news/1")
        self.assertEqual(entry["channel_label"], "@news")
        self.assertEqual(pipe.reasons(), ["digest"])
        self.assertEqual(pipe.log_decision.call_args.args[2], "queued")

    async def test_quiet_hours_queue_the_story_and_the_reason_says_so(self):
        pipe = Pipeline(self)
        for name in ("quiet_hours", "timezone"):
            self.addCleanup(listener.runtime.reset, name)
        listener.runtime.set_value("quiet_hours", "23:00-08:00")
        with patch.object(listener, "utc_now", return_value=datetime(2026, 10, 15, 3, 0, tzinfo=UTC)):
            await pipe.send()
        pipe.client.send_message.assert_not_awaited()
        self.assertIsNotNone(pipe.finalize.call_args.kwargs["queue_entry"])
        self.assertEqual(pipe.reasons(), ["quiet_hours"])

    async def test_outside_quiet_hours_the_story_is_sent_normally(self):
        pipe = Pipeline(self)
        for name in ("quiet_hours", "timezone"):
            self.addCleanup(listener.runtime.reset, name)
        listener.runtime.set_value("quiet_hours", "23:00-08:00")
        with patch.object(listener, "utc_now", return_value=datetime(2026, 10, 15, 12, 0, tzinfo=UTC)):
            await pipe.send()
        pipe.client.send_message.assert_awaited_once()
        self.assertIsNone(pipe.finalize.call_args.kwargs.get("queue_entry"))
        self.assertEqual(pipe.reasons(), ["published"])

    async def test_queued_story_still_updates_the_cluster_centroid(self):
        rows = [(7, [1.0, 0.0], 1)]
        pipe = Pipeline(self, embedding=(0.99, 0.1), clusters_rows=rows)
        self.addCleanup(listener.runtime.reset, "delivery_mode")
        listener.runtime.set_value("delivery_mode", "digest")
        await pipe.send()
        pipe.update_centroid.assert_called_once()
        self.assertEqual(pipe.claim.call_args.args[0], 7)

    async def test_text_with_a_muted_word_is_skipped_before_any_work(self):
        pipe = Pipeline(self, muted=["новость"])
        await pipe.send()
        pipe.client.send_message.assert_not_awaited()
        pipe.embed.assert_not_awaited()
        pipe.claim.assert_not_called()
        self.assertEqual(pipe.reasons(), ["muted"])

    async def test_muted_words_are_reloaded_when_the_channel_list_is_refreshed(self):
        pipe = Pipeline(self)
        refresh, _, _ = listener.register_listener(pipe.client)
        pipe.mute_words.return_value = ["новость"]
        await refresh(force=True)
        await pipe.send()
        self.assertEqual(pipe.reasons(), ["muted"])

    async def test_repost_of_published_story_is_skipped(self):
        pipe = Pipeline(self, origin_seen=True)
        forward = SimpleNamespace(channel_post=5, from_id=object())
        await pipe.send(fwd_from=forward)
        pipe.client.send_message.assert_not_awaited()
        self.assertEqual(pipe.reasons(), ["repost_duplicate"])

    def test_origin_key_uses_forward_source(self):
        forward = SimpleNamespace(channel_post=5, from_id=object())
        message = SimpleNamespace(id=9, fwd_from=forward)
        with patch.object(listener, "get_peer_id", return_value=-100777):
            self.assertEqual(listener.make_origin_key("-10042", [message]), "-100777:5")
        plain = SimpleNamespace(id=9, fwd_from=None)
        self.assertEqual(listener.make_origin_key("-10042", [plain]), "-10042:9")

    async def test_match_above_threshold_joins_cluster_and_updates_centroid(self):
        rows = [(7, [1.0, 0.0], 1)]
        pipe = Pipeline(self, embedding=(0.99, 0.1), clusters_rows=rows)
        await pipe.send()
        self.assertEqual(pipe.claim.call_args.args[0], 7)
        pipe.create_cluster.assert_not_called()
        pipe.update_centroid.assert_called_once()
        self.assertEqual(pipe.update_centroid.call_args.args[2], 2)

    async def test_match_below_threshold_creates_new_cluster(self):
        rows = [(7, [1.0, 0.0], 1)]
        pipe = Pipeline(self, embedding=(0.9, 0.436), clusters_rows=rows)
        await pipe.send()
        self.assertEqual(pipe.claim.call_args.args[0], 99)
        pipe.update_centroid.assert_not_called()

    async def test_protected_channel_media_falls_back_to_text(self):
        pipe = Pipeline(self)
        pipe.client.send_file.side_effect = ChatForwardsRestrictedError(request=None)
        event = event_for()
        event.message.media = MessageMediaPhoto()
        await pipe.client.handlers[events.NewMessage](event)
        pipe.client.send_message.assert_awaited_once()
        self.assertIn(TEXT, pipe.client.send_message.await_args.args[1])
        pipe.finalize.assert_called_once()
        pipe.release.assert_not_called()
        self.assertEqual(pipe.reasons(), ["published"])

    async def test_rejected_send_releases_claim_instead_of_leaving_it_pending(self):
        pipe = Pipeline(self)
        pipe.client.send_message.side_effect = ChatWriteForbiddenError(request=None)
        await pipe.send()
        pipe.release.assert_called_once_with(5)
        pipe.finalize.assert_not_called()

    async def test_network_failure_keeps_claim_pending(self):
        pipe = Pipeline(self)
        pipe.client.send_message.side_effect = ConnectionError("lost")
        await pipe.send()
        pipe.release.assert_not_called()
        pipe.finalize.assert_not_called()

    async def test_old_backlog_message_is_skipped_as_too_old(self):
        pipe = Pipeline(self)
        old = datetime.now(UTC) - timedelta(hours=config.BACKFILL_MAX_AGE_HOURS + 1)
        await pipe.send(date=old)
        pipe.client.send_message.assert_not_awaited()
        self.assertEqual(pipe.reasons(), ["too_old"])

    async def test_recent_message_passes_age_check(self):
        pipe = Pipeline(self)
        await pipe.send(date=datetime.now(UTC) - timedelta(minutes=5))
        pipe.client.send_message.assert_awaited_once()

    async def test_sends_are_paced(self):
        pipe = Pipeline(self)
        sleeps = []

        async def fake_sleep(seconds):
            sleeps.append(seconds)

        with patch.object(config, "SEND_MIN_INTERVAL_SEC", 3), \
             patch.object(listener.asyncio, "sleep", new=fake_sleep):
            await pipe.send(message_id=1)
            await pipe.send(message_id=2)
        self.assertEqual(pipe.client.send_message.await_count, 2)
        self.assertEqual(len(sleeps), 1)
        self.assertGreater(sleeps[0], 2.5)

    async def test_poison_message_is_skipped_after_max_attempts(self):
        pipe = Pipeline(self)
        pipe.embed.side_effect = RuntimeError("offline")
        with patch.object(config, "GIVEUP_MIN_AGE_SEC", 0):
            for _ in range(config.MAX_PROCESS_ATTEMPTS):
                await pipe.send()
        self.assertEqual(pipe.reasons(), ["error_giveup"])

    async def test_short_outage_never_drops_a_message(self):
        pipe = Pipeline(self)
        pipe.embed.side_effect = RuntimeError("offline")
        for _ in range(config.MAX_PROCESS_ATTEMPTS + 3):
            await pipe.send()
        self.assertEqual(pipe.reasons(), [])

    async def test_link_preview_is_not_sent_as_media(self):
        pipe = Pipeline(self)
        event = event_for()
        event.message.media = SimpleNamespace(kind="MessageMediaWebPage")
        await pipe.client.handlers[events.NewMessage](event)
        pipe.client.send_file.assert_not_awaited()
        pipe.client.send_message.assert_awaited_once()

    async def test_runtime_threshold_override_is_used(self):
        rows = [(7, [1.0, 0.0], 1)]
        pipe = Pipeline(self, embedding=(0.9, 0.436), clusters_rows=rows)
        with patch.object(listener.runtime, "get", side_effect=lambda n: {
                "cluster_threshold": 0.85, "fuzzy_threshold": 88}[n]):
            await pipe.send()
        self.assertEqual(pipe.claim.call_args.args[0], 7)


if __name__ == "__main__":
    unittest.main()

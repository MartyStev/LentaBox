import asyncio
import html
import logging
import re
import time
from datetime import datetime, timedelta, UTC

from telethon import events
from telethon.errors import ChatForwardsRestrictedError, RPCError
from telethon.tl.types import MessageMediaDocument, MessageMediaPhoto
from telethon.utils import get_peer_id

import config
from db import channels
from db import clusters
from db import cursors
from db import metrics
from db import mute_words
from db import posts
from db import publications
from core import quiet, runtime
from core.digest import headline
from core.i18n import t
from core.cleaning import is_ad, matching_text
from core.embeddings import embed
from core.entities import to_html
from core.filters import matches as has_muted_word
from core.links import source_link
from core.similarity import best_cluster_match, best_fuzzy_score, merge_centroid
from core.text import hash_text, normalize_text


log = logging.getLogger("stenabot")
CHANNELS_REFRESH_SEC = getattr(config, "CHANNELS_REFRESH_SEC", 30)
BACKFILL_INTERVAL_SEC = getattr(config, "BACKFILL_INTERVAL_SEC", 60)
BACKFILL_BATCH_SIZE = getattr(config, "BACKFILL_BATCH_SIZE", 500)
BACKFILL_SETTLE_SEC = getattr(config, "BACKFILL_SETTLE_SEC", 5)
MESSAGE_LIMIT = 4000  # Leave room below Telegram's 4096-character limit.


def is_sendable_media(media) -> bool:
    """Photos and documents can be re-sent; link previews, polls, etc. cannot."""
    return isinstance(media, (MessageMediaPhoto, MessageMediaDocument))


def message_age(messages):
    """Age of the newest message in the group, or None if the date is unknown."""
    dates = [getattr(m, "date", None) for m in messages]
    dates = [d for d in dates if d is not None]
    if not dates:
        return None
    newest = max(dates)
    if newest.tzinfo is None:
        newest = newest.replace(tzinfo=UTC)
    return datetime.now(UTC) - newest


async def resolve_channel(client, channel_id, username=None):
    """Find a channel entity by username, id, or among the account's dialogs."""
    channel_id = str(channel_id)
    for hint in (username or None, int(channel_id)):
        if hint is None:
            continue
        try:
            return await client.get_entity(hint)
        except Exception:
            log.debug("Could not resolve channel %s via %r", channel_id, hint)
    for dialog in await client.get_dialogs():
        if str(get_peer_id(dialog.entity)) == channel_id:
            return dialog.entity
    raise RuntimeError(f"Could not resolve channel {channel_id}")


def make_origin_key(channel_id, messages) -> str:
    """Source key: the original of a repost, or the post itself if it is not forwarded."""
    for message in messages:
        forward = getattr(message, "fwd_from", None)
        post_id = getattr(forward, "channel_post", None)
        if forward is not None and post_id and getattr(forward, "from_id", None) is not None:
            try:
                return f"{get_peer_id(forward.from_id)}:{post_id}"
            except Exception:
                break
    return f"{channel_id}:{messages[0].id}"


def _utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def build_content(text: str, footer: str, limit: int, rich_html: str | None = None) -> str:
    """Escape source text and reserve space for the footer and truncation mark.

    ``rich_html`` is the original formatting (see core.entities). It is used only when it fits whole:
    cutting HTML in the middle of a tag would break the message, so longer texts fall back to plain text.
    """
    text = text.strip()
    visible_footer = html.unescape(re.sub(r"<[^>]*>", "", footer))
    budget = max(0, limit - len(visible_footer.encode("utf-16-le")) // 2)
    if rich_html and _utf16_len(rich_html) <= budget:
        return (rich_html.strip() + footer).strip()
    text_units = len(text.encode("utf-16-le")) // 2
    if text_units > budget:
        mark = t("truncated_mark")
        budget = max(0, budget - _utf16_len(mark))
        used = 0
        prefix = []
        for char in text:
            char_units = len(char.encode("utf-16-le")) // 2
            if used + char_units > budget:
                break
            prefix.append(char)
            used += char_units
        text = "".join(prefix).rstrip() + mark
    return (html.escape(text) + footer).strip()


def utc_now() -> datetime:
    return datetime.now(UTC)


def channel_label(channel: dict) -> str:
    """@username, or the title for channels without one (not HTML-escaped)."""
    username = (channel.get("username") or "").strip().lstrip("@")
    return f"@{username}" if username else (channel.get("title") or t("unknown_channel"))


def deferral_reason() -> str | None:
    """Why a story must wait for a digest instead of being posted now: "digest", "quiet_hours" or None."""
    if runtime.get("delivery_mode") == "digest":
        return "digest"
    if quiet.in_quiet(utc_now(), runtime.quiet_window(), runtime.zone()):
        return "quiet_hours"
    return None


def build_footer(channel: dict, message_id: int) -> str:
    username = (channel.get("username") or "").strip().lstrip("@")
    label = html.escape(channel_label(channel))
    link = source_link(username, channel["telegram_id"], message_id)

    footer = f"\n\n<b>📢 {t('footer_channel')}:</b> {label}"
    if link:
        footer += f'\n🔗 <a href="{link}">{t("footer_original")}</a>'
    return footer


def register_listener(client, alerter=None):
    channel_list = channels.list_channels()
    channel_map = {str(ch["telegram_id"]): ch for ch in channel_list}
    muted: list[str] = list(mute_words.list_words())
    last_refresh_ts = time.monotonic()
    processing_lock = asyncio.Lock()
    scan_lock = asyncio.Lock()
    failures: dict[tuple[str, int], tuple[int, float]] = {}
    last_send_ts = 0.0

    async def pace_sends():
        """Pause between sends so that draining the queue does not turn into a flood."""
        nonlocal last_send_ts
        wait = last_send_ts + config.SEND_MIN_INTERVAL_SEC - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        last_send_ts = time.monotonic()

    async def alert(key, text):
        if alerter is not None:
            await alerter.notify(key, text)

    log.info("INIT: listening channels %s", set(channel_map))

    async def refresh_channels(force: bool = False):
        nonlocal channel_map, last_refresh_ts
        now = time.monotonic()
        if not force and now - last_refresh_ts < CHANNELS_REFRESH_SEC:
            return
        updated_list = await asyncio.to_thread(channels.list_channels)
        channel_map = {str(ch["telegram_id"]): ch for ch in updated_list}
        muted[:] = await asyncio.to_thread(mute_words.list_words)
        last_refresh_ts = now
        log.info("CHANNELS: refreshed (%s channels)", len(channel_map))

    async def send_post(text_content, media, footer, rich_html=None):
        """Send media with a caption; fall back to text if the media cannot be re-sent."""
        if media:
            try:
                await client.send_file(
                    config.target_chat_id,
                    media if len(media) > 1 else media[0],
                    caption=build_content(text_content, footer, config.CAPTION_LIMIT, rich_html),
                    parse_mode="html",
                )
                return
            except (ChatForwardsRestrictedError, TypeError, ValueError) as exc:
                # Protected channels forbid re-sending their media; the text is still ours to post.
                log.warning("Media not re-sendable, posting text only: %s", exc)
        await client.send_message(
            config.target_chat_id,
            build_content(text_content, footer, MESSAGE_LIMIT, rich_html),
            parse_mode="html",
        )

    async def process(channel_id, messages):
        async with processing_lock:
            channel_id = str(channel_id)
            messages = sorted(messages, key=lambda message: message.id)
            message_id = messages[0].id
            excerpt = None

            async def log_decision(decision, reason, cluster_id=None,
                                   fuzzy_score=None, cluster_score=None):
                try:
                    await asyncio.to_thread(
                        metrics.log_decision, channel_id, message_id,
                        decision, reason, cluster_id, fuzzy_score,
                        cluster_score, excerpt,
                    )
                except Exception:
                    log.exception("Failed to record decision %s:%s", channel_id, message_id)

            try:
                await refresh_channels()
                if channel_id not in channel_map:
                    return True

                text_message = next((message for message in messages if message.message), None)
                text_content = text_message.message.strip() if text_message else ""
                rich_html = to_html(text_message.message, getattr(text_message, "entities", None)) if text_message else None
                media = [
                    message.media for message in messages
                    if message.media and is_sendable_media(message.media)
                ]
                if not text_content:
                    await log_decision("skip", "no_text")
                    return True
                excerpt = normalize_text(text_content)[:config.EXCERPT_LIMIT]

                if has_muted_word(text_content, muted):
                    await log_decision("skip", "muted")
                    return True

                age = message_age(messages)
                if age is not None and age > timedelta(hours=config.BACKFILL_MAX_AGE_HOURS):
                    await log_decision("skip", "too_old")
                    return True

                if config.AD_FILTER_ENABLED and is_ad(text_content):
                    await log_decision("skip", "advertisement")
                    return True

                text_body = matching_text(text_content, config.BODY_LIMIT)
                text_hash = hash_text(text_content)
                origin_key = make_origin_key(channel_id, messages)

                if await asyncio.to_thread(posts.post_exists, text_hash, config.EXACT_WINDOW_SIZE):
                    await log_decision("skip", "exact_duplicate")
                    return True

                if await asyncio.to_thread(posts.origin_seen, origin_key):
                    await log_decision("skip", "repost_duplicate")
                    return True

                recent_texts = await asyncio.to_thread(posts.get_recent_texts, config.FUZZ_WINDOW_SIZE)
                best_fuzzy = best_fuzzy_score(
                    text_body,
                    [matching_text(old, config.BODY_LIMIT) for old in recent_texts],
                )
                if best_fuzzy >= runtime.get("fuzzy_threshold"):
                    await log_decision("skip", "fuzzy_duplicate", fuzzy_score=best_fuzzy)
                    return True

                if len(text_body) < 20:
                    await log_decision("skip", "too_short")
                    return True

                embedding = await embed(text_body)
                recent_clusters = await asyncio.to_thread(clusters.get_recent_clusters, 48, 200)
                best_cluster_id, best_score = best_cluster_match(embedding, recent_clusters)

                cluster_id = None
                if best_cluster_id is not None and best_score >= runtime.get("cluster_threshold"):
                    cluster_id = best_cluster_id

                merged_into_existing = cluster_id is not None
                if cluster_id is None:
                    cluster_id = await asyncio.to_thread(clusters.create_cluster, embedding)

                claim_id = await asyncio.to_thread(
                    publications.claim, cluster_id, channel_id, message_id,
                )
                if claim_id is None:
                    pending = await asyncio.to_thread(
                        publications.has_pending_conflict,
                        cluster_id, channel_id, message_id,
                    )
                    await log_decision("skip", "pending_review" if pending else "already_sent",
                                       cluster_id=cluster_id, cluster_score=best_score)
                    return not pending

                if merged_into_existing and config.CENTROID_UPDATE:
                    centroid, count = next(
                        ((c, n) for cid, c, n in recent_clusters if cid == cluster_id),
                        (None, 1),
                    )
                    if centroid is not None:
                        await asyncio.to_thread(
                            clusters.update_centroid, cluster_id,
                            merge_centroid(centroid, count, embedding, config.CENTROID_MAX_WEIGHT),
                            count + 1,
                        )

                defer = deferral_reason()
                if defer:
                    channel = channel_map[channel_id]
                    entry = {
                        "headline": headline(text_content),
                        "link": source_link(channel.get("username"), channel["telegram_id"], message_id),
                        "channel_label": channel_label(channel),
                    }
                    try:
                        await asyncio.to_thread(
                            publications.finalize, claim_id, cluster_id, channel_id,
                            message_id, text_hash, text_content, origin_key, queue_entry=entry,
                        )
                    except Exception:
                        # Nothing was sent, so the claim can be freed and the message retried.
                        await asyncio.to_thread(publications.release, claim_id)
                        raise
                    await log_decision("queued", defer, cluster_id=cluster_id,
                                       fuzzy_score=best_fuzzy, cluster_score=best_score)
                    log.info("[QUEUE:%s] cluster=%s | %s:%s", defer, cluster_id, channel_id, message_id)
                    failures.pop((channel_id, message_id), None)
                    return True

                footer = build_footer(channel_map[channel_id], message_id)
                try:
                    await pace_sends()
                    await send_post(text_content, media, footer, rich_html)
                except RPCError as exc:
                    # Telegram rejected the request, so nothing was published:
                    # free the claim and let the usual retry logic handle it.
                    await asyncio.to_thread(publications.release, claim_id)
                    log.warning("Send rejected for %s:%s, claim released: %s",
                                channel_id, message_id, exc)
                    raise
                except Exception:
                    # A network error may arrive after Telegram accepted the post.
                    # Keep the claim for manual reconciliation in that case.
                    log.exception("Send outcome unknown for claim %s", claim_id)
                    await alert("send_unknown", t("alert_send_unknown", claim_id=claim_id))
                    raise

                # A failed finalization after Telegram accepts the send leaves
                # the claim pending so an automatic retry cannot duplicate it.
                await asyncio.to_thread(
                    publications.finalize, claim_id, cluster_id, channel_id,
                    message_id, text_hash, text_content, origin_key,
                )
                await log_decision("sent", "published", cluster_id=cluster_id,
                                   fuzzy_score=best_fuzzy, cluster_score=best_score)
                log.info("[SEND] cluster=%s | %s:%s", cluster_id, channel_id, message_id)
                failures.pop((channel_id, message_id), None)
                return True
            except Exception as exc:
                log.exception("Handler error")
                key = (channel_id, message_id)
                attempts, first_seen = failures.get(key, (0, time.monotonic()))
                attempts += 1
                failures[key] = (attempts, first_seen)
                if attempts == 1:
                    await alert("process_error", t("alert_process_error", channel=channel_id, message=message_id, error=repr(exc)))
                # A brief network or embedding-server failure must not cost us the news item.
                if (attempts >= config.MAX_PROCESS_ATTEMPTS
                        and time.monotonic() - first_seen >= config.GIVEUP_MIN_AGE_SEC):
                    failures.pop(key, None)
                    await log_decision("skip", "error_giveup")
                    await alert(
                        "giveup",
                        t("alert_giveup", channel=channel_id, message=message_id, attempts=config.MAX_PROCESS_ATTEMPTS),
                    )
                    return True
                return False

    async def scan_channel(channel_id, channel):
        entity = await resolve_channel(client, channel_id, channel.get("username"))

        cursor = await asyncio.to_thread(cursors.get, channel_id)
        if cursor is None:
            latest = await client.get_messages(entity, limit=1)
            baseline = latest[0].id if latest else 0
            await asyncio.to_thread(cursors.initialize, channel_id, baseline)
            log.info("BACKFILL: initialized channel %s at message %s", channel_id, baseline)
            return

        group = []
        group_id = None
        processed = 0

        async def flush_group():
            nonlocal processed
            message_date = getattr(group[-1], "date", None)
            if message_date is not None:
                if message_date.tzinfo is None:
                    message_date = message_date.replace(tzinfo=UTC)
                if datetime.now(UTC) - message_date < timedelta(seconds=BACKFILL_SETTLE_SEC):
                    return False
            if not await process(channel_id, group):
                return False
            await asyncio.to_thread(cursors.advance, channel_id, group[-1].id)
            processed += len(group)
            return True

        async for message in client.iter_messages(entity, min_id=cursor, reverse=True):
            if group and (group_id is None or message.grouped_id != group_id):
                if not await flush_group():
                    return
                if processed >= BACKFILL_BATCH_SIZE:
                    return
                group = []

            group.append(message)
            group_id = message.grouped_id

        if group:
            await flush_group()

    async def catch_up_once():
        async with scan_lock:
            await refresh_channels(force=True)
            for channel_id, channel in list(channel_map.items()):
                try:
                    await scan_channel(channel_id, channel)
                except Exception:
                    log.exception("BACKFILL: failed for channel %s", channel_id)

    async def backfill_loop():
        while True:
            try:
                await catch_up_once()
            except Exception:
                log.exception("BACKFILL: scan failed")
            await asyncio.sleep(BACKFILL_INTERVAL_SEC)

    @client.on(events.NewMessage(incoming=True))
    async def message_handler(event):
        if event.message.grouped_id:
            return
        try:
            channel_id = get_peer_id(await event.get_chat())
        except Exception:
            log.exception("Could not identify message source")
            return
        await process(channel_id, [event.message])

    @client.on(events.Album)
    async def album_handler(event):
        try:
            channel_id = get_peer_id(await event.get_chat())
        except Exception:
            log.exception("Could not identify album source")
            return
        await process(channel_id, event.messages)

    return refresh_channels, catch_up_once, backfill_loop

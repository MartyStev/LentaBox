"""Background tasks: subscription auto-sync and silence monitoring."""

import asyncio
import logging
import os
from datetime import datetime, timedelta, UTC

import config
from db import channels
from db import cursors
from db import digest as digest_db
from db import metrics
from db import posts
from db import publications
from db import instance_lock
from core import quiet, runtime
from core.digest import format_digest
from core.i18n import t
from core.sdnotify import sd_notify
from core.links import source_link
from handlers.listener import resolve_channel
from handlers.subscriptions import SubscriptionManager, apply_sync

log = logging.getLogger("stenabot.maintenance")


async def watchdog_loop():
    """Tell systemd the event loop is alive; if it hangs, WatchdogSec restarts the service."""
    while True:
        sd_notify("WATCHDOG=1")
        await asyncio.sleep(config.WATCHDOG_SEC)


async def autosync_once(manager: SubscriptionManager, alerter=None) -> bool:
    """One auto-sync pass; True if the channel list changed."""
    if not runtime.get("autosync"):
        return False
    plan, removed = await apply_sync(manager._fetch_subs)
    if not plan.to_add and not removed:
        return False
    await manager._changed()
    if alerter is not None:
        report = SubscriptionManager._sync_report(t("autosync_report_title"), plan, removed)
        await alerter.notify("autosync", report, cooldown=0)
    return True


async def autosync_loop(manager: SubscriptionManager, alerter=None):
    while True:
        await asyncio.sleep(config.AUTOSYNC_INTERVAL_SEC)
        try:
            await autosync_once(manager, alerter)
        except Exception:
            log.exception("Auto-sync failed")


async def silence_check_once(alerter, now=None) -> bool:
    """Alert if nothing has been published for a long time while the channel list is non-empty."""
    now = now or datetime.now(UTC)
    rows = await asyncio.to_thread(channels.list_channels)
    if not rows:
        return False
    last = await asyncio.to_thread(posts.last_saved_at)
    if last is None:
        return False
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    if now - last < timedelta(hours=config.SILENCE_ALERT_HOURS):
        return False
    hours = int((now - last).total_seconds() // 3600)
    return await alerter.notify(
        "silence",
        t("alert_silence", hours=hours),
        cooldown=config.SILENCE_ALERT_HOURS * 3600,
    )


async def instance_lock_loop(alerter=None, check=instance_lock.still_held, interval=60):
    """Terminate the process if the single-instance lock has been lost."""
    while True:
        await asyncio.sleep(interval)
        if await asyncio.to_thread(check):
            continue
        log.critical("Single-instance lock lost, shutting down the process")
        if alerter is not None:
            await alerter.notify("lock_lost", t("alert_lock_lost"), cooldown=0)
        os._exit(1)


async def silence_loop(alerter):
    while True:
        await asyncio.sleep(config.SILENCE_CHECK_SEC)
        try:
            await silence_check_once(alerter)
        except Exception:
            log.exception("Silence check failed")


def _channel_label(row) -> str:
    return (f"@{row['username']}" if row.get("username")
            else row.get("title") or str(row.get("channel_id") or row.get("telegram_id")))


def _as_utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


async def stall_check_once(client, alerter, now=None, fetch_latest=None):
    """Find channels whose cursor has not moved for a long time although the channel has new messages.

    Returns the list of channel_ids of stalled channels. fetch_latest(channel) ->
    the channel's latest message; by default it asks Telegram.
    """
    now = now or datetime.now(UTC)
    threshold = timedelta(hours=config.STALL_ALERT_HOURS)
    channel_rows = {str(c["telegram_id"]): c for c in await asyncio.to_thread(channels.list_channels)}
    stalled = []

    async def default_fetch_latest(channel):
        entity = await resolve_channel(client, channel["telegram_id"], channel.get("username"))
        messages = await client.get_messages(entity, limit=1)
        return messages[0] if messages else None

    fetch_latest = fetch_latest or default_fetch_latest
    for cursor in await asyncio.to_thread(cursors.list_all):
        channel = channel_rows.get(cursor["channel_id"])
        if channel is None or now - _as_utc(cursor["updated_at"]) < threshold:
            continue
        try:
            latest = await fetch_latest(channel)
        except Exception:
            log.exception("STALL: cannot read channel %s", cursor["channel_id"])
            continue
        if latest is None or latest.id <= cursor["last_message_id"]:
            continue
        latest_date = getattr(latest, "date", None)
        if latest_date is not None and now - _as_utc(latest_date) < threshold:
            continue  # The new message appeared recently; catch-up simply has not reached it yet.
        stalled.append(cursor["channel_id"])
        hours = int((now - _as_utc(cursor["updated_at"])).total_seconds() // 3600)
        await alerter.notify(
            f"stall:{cursor['channel_id']}",
            t("alert_stall", channel=_channel_label(channel), hours=hours,
              cursor=cursor["last_message_id"], latest=latest.id),
            cooldown=config.STALL_ALERT_HOURS * 3600,
        )
    return stalled


async def stall_loop(client, alerter):
    while True:
        await asyncio.sleep(config.STALL_CHECK_SEC)
        try:
            await stall_check_once(client, alerter)
        except Exception:
            log.exception("Stall check failed")


async def expire_claims_once(alerter=None):
    """Close pending claims older than CLAIM_EXPIRE_HOURS and notify the owner."""
    rows = await asyncio.to_thread(publications.expire_pending, config.CLAIM_EXPIRE_HOURS)
    if rows and alerter is not None:
        lines = [t("alert_claims_expired", count=len(rows), hours=config.CLAIM_EXPIRE_HOURS)]
        for row in rows[:10]:
            link = source_link(row["username"], row["channel_id"], row["message_id"])
            lines.append(f"#{row['id']} {_channel_label(row)} {link or row['message_id']}")
        await alerter.notify("claims_expired", "\n".join(lines), cooldown=0)
    return rows


async def expire_claims_loop(alerter=None):
    while True:
        try:
            await expire_claims_once(alerter)
        except Exception:
            log.exception("Closing stale claims failed")
        await asyncio.sleep(config.CLAIM_EXPIRE_CHECK_SEC)


def _digest_due(now: datetime, last_sent) -> bool:
    """Instant mode only flushes what quiet hours held back; digest mode waits for its period."""
    if runtime.get("delivery_mode") != "digest" or last_sent is None:
        return True
    if last_sent.tzinfo is None:
        last_sent = last_sent.replace(tzinfo=UTC)
    return now - last_sent >= timedelta(hours=runtime.get("digest_hours"))


async def digest_once(client, alerter, now=None, force: bool = False) -> int:
    """Send the queued stories as a digest if it is due; returns how many stories were sent.

    Rows are marked only after every part reached the chat. If a part fails, nothing is marked and the next
    pass sends the whole digest again: a repeated headline is better than a lost one.
    """
    now = now or datetime.now(UTC)
    if not await asyncio.to_thread(digest_db.count_unsent):
        return 0
    if not force:
        if quiet.in_quiet(now, runtime.quiet_window(), runtime.zone()):
            return 0
        if not _digest_due(now, await asyncio.to_thread(digest_db.last_sent_at)):
            return 0
    rows = await asyncio.to_thread(digest_db.list_unsent, config.DIGEST_BATCH)
    if not rows:
        return 0
    try:
        for index, text in enumerate(format_digest(rows)):
            if index:
                await asyncio.sleep(config.DIGEST_PART_PAUSE_SEC)
            await client.send_message(config.target_chat_id, text, parse_mode="html", link_preview=False)
        await asyncio.to_thread(digest_db.mark_sent, [row["id"] for row in rows])
    except Exception as exc:
        log.exception("Digest send failed")
        if alerter is not None:
            await alerter.notify("digest_failed", t("alert_digest_failed", error=repr(exc)))
        return 0
    log.info("DIGEST: sent %s stories", len(rows))
    return len(rows)


async def digest_loop(client, alerter):
    while True:
        try:
            await digest_once(client, alerter)
        except Exception:
            log.exception("Digest pass failed")
        await asyncio.sleep(config.DIGEST_CHECK_SEC)


async def purge_loop():
    while True:
        try:
            deleted = await asyncio.to_thread(
                metrics.purge_old_decisions, config.DECISIONS_RETENTION_DAYS,
            )
            if deleted:
                log.info("Old decisions deleted: %s", deleted)
        except Exception:
            log.exception("bot_decisions cleanup failed")
        try:
            await asyncio.to_thread(digest_db.purge_sent, config.DIGEST_RETENTION_DAYS)
        except Exception:
            log.exception("digest_queue cleanup failed")
        await asyncio.sleep(24 * 3600)

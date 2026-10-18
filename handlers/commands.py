from telethon import events
from telethon.utils import get_peer_id
import asyncio
import re
import config
from db import channels
from db import metrics
from db import digest as digest_db
from db import mute_words
from db import publications
import db.settings as settings_db
from core import i18n, runtime
from core.channel_ref import parse_channel_ref
from core.i18n import t
from core.links import source_link

MESSAGE_LINK_RE = re.compile(r"t\.me/(?:c/)?[^/\s]+/(\d+)")


def register_commands(client, owner_id, on_channels_changed=None, flush_digest=None):

    # --- /menu ---
    @client.on(events.NewMessage(from_users=[owner_id], pattern=r"^/menu$"))
    async def menu(event):
        await event.respond(t("menu_text"), parse_mode=None)

    # --- /list ---
    @client.on(events.NewMessage(from_users=[owner_id], pattern=r"^/list$"))
    async def list_channels(event):
        rows = await asyncio.to_thread(channels.list_channels)
        if not rows:
            await event.respond(t("list_empty"))
            return
        try:
            sent = await asyncio.to_thread(metrics.get_sent_counts, 24)
        except Exception:
            sent = {}
        lines = []
        for number, c in enumerate(rows, start=1):
            name = f"@{c['username']}" if c["username"] else f"{c['title']} ({c['telegram_id']})"
            tag = " 🔄" if c.get("source") == "sync" else ""
            lines.append(f"{number}. {name}{tag} — " + t("list_count", count=sent.get(str(c["telegram_id"]), 0)))
        await event.respond(
            t("list_header", count=len(rows)) + "\n" + "\n".join(lines) + "\n" + t("list_footer"),
            parse_mode=None,
        )

    # --- /add ---
    @client.on(events.NewMessage(from_users=[owner_id], pattern=r"^/add(?:\s+(.+))?$"))
    async def add_channel(event):
        link = (event.pattern_match.group(1) or "").strip()
        if not link:
            await event.reply(t("add_usage"))
            return
        ref = parse_channel_ref(link)
        if ref is None:
            await event.reply(t("add_not_channel"), parse_mode=None)
            return
        if ref.kind == "invite":
            await event.reply(t("add_invite"), parse_mode=None)
            return
        try:
            entity = await client.get_entity(ref.value)
            if not getattr(entity, "broadcast", False):
                await event.reply(t("add_not_broadcast"), parse_mode=None)
                return
            channel_id = get_peer_id(entity)

            username = getattr(entity, "username", None)
            title = getattr(entity, "title", None)

            await asyncio.to_thread(channels.add_channel, channel_id, username, title)
            await asyncio.to_thread(channels.clear_exclusion, channel_id)
            if on_channels_changed:
                await on_channels_changed(force=True)
            label = f"@{username}" if username else (title or str(channel_id))
            await event.reply(t("add_ok", label=label), parse_mode=None)

        except Exception as e:
            await event.reply(t("add_error", error=e))

    # --- /remove ---
    @client.on(events.NewMessage(from_users=[owner_id], pattern=r"^/remove(?:\s+(.+))?$"))
    async def remove_channel(event):
        link = (event.pattern_match.group(1) or "").strip()
        if not link:
            await event.reply(t("remove_usage"))
            return
        try:
            entity = await client.get_entity(link)
            channel_id = get_peer_id(entity)
            await asyncio.to_thread(channels.remove_channel, channel_id)
            await asyncio.to_thread(channels.add_exclusion, channel_id)
            if on_channels_changed:
                await on_channels_changed(force=True)
            await event.reply(t("remove_ok"))
        except Exception as e:
            await event.reply(t("remove_error", error=e))

    # --- /stats ---
    @client.on(events.NewMessage(from_users=[owner_id], pattern=r"^/stats(?:\s+(channels|каналы))?$"))
    async def stats(event):
        try:
            if event.pattern_match.group(1):
                rows = await asyncio.to_thread(metrics.get_channel_stats, 24)
                lines = [t("stats_channels_header")]
                for row in rows[:30]:
                    name = (f"@{row['username']}" if row["username"]
                            else row["title"] or row["channel_id"])
                    lines.append(f"• {name}: {row['sent'] + row.get('queued', 0)} / {row['skipped']}")
                if len(lines) == 1:
                    lines.append(t("stats_no_data"))
                await event.reply("\n".join(lines), parse_mode=None)
                return

            totals, reason_rows = await asyncio.to_thread(
                metrics.get_stats_last_hours,
                24
            )

            lines = [
                t("stats_header"),
                t("stats_total", count=totals.get("total", 0)),
                t("stats_sent", count=totals.get("sent", 0)),
            ]
            if totals.get("queued"):
                lines.append(t("stats_queued", count=totals["queued"]))
            lines += [t("stats_skipped", count=totals.get("skipped", 0)), "", t("stats_reasons")]

            if reason_rows:
                for row in reason_rows[:10]:
                    lines.append(f"• {row['reason']}: {row['cnt']}")
            else:
                lines.append(t("stats_no_data"))

            await event.reply("\n".join(lines), parse_mode=None)
        except Exception as e:
            await event.reply(t("stats_error", error=e), parse_mode=None)

    # --- /why ---
    @client.on(events.NewMessage(from_users=[owner_id], pattern=r"^/why(?:\s+(.+))?$"))
    async def why(event):
        arg = (event.pattern_match.group(1) or "").strip()
        link = MESSAGE_LINK_RE.search(arg)
        if link:
            arg = link.group(1)
        if not arg.isdigit():
            await event.reply(t("why_usage"), parse_mode=None)
            return

        msg_id = int(arg)

        try:
            rows = await asyncio.to_thread(metrics.get_why_by_message_id, msg_id, 5)
            if not rows:
                await event.reply(t("why_none", id=msg_id), parse_mode=None)
                return

            lines = [t("why_header", id=msg_id)]
            for row in rows:
                lines.append(
                    f"• {row['created_at']} | channel={row['channel_id']} | "
                    f"{row['decision']} ({row['reason']}) | "
                    f"cluster={row['cluster_id']} | "
                    f"fuzzy={row['fuzzy_score']} | sim={row['cluster_score']}"
                )
                if row.get("excerpt"):
                    lines.append(f"  «{row['excerpt']}»")

            await event.reply("\n".join(lines), parse_mode=None)
        except Exception as e:
            await event.reply(t("why_error", error=e), parse_mode=None)

    # --- /threshold ---
    @client.on(events.NewMessage(from_users=[owner_id], pattern=r"^/threshold(?:\s+(.+))?$"))
    async def threshold(event):
        names = {"cluster": "cluster_threshold", "fuzzy": "fuzzy_threshold"}
        parts = (event.pattern_match.group(1) or "").split()
        if not parts:
            await event.reply(
                t("threshold_show", cluster=runtime.get("cluster_threshold"), cluster_default=config.CLUSTER_THRESHOLD,
                  fuzzy=runtime.get("fuzzy_threshold"), fuzzy_default=config.FUZZ_DUP_THRESHOLD),
                parse_mode=None,
            )
            return
        try:
            if parts == ["reset"]:
                for key in names.values():
                    runtime.reset(key)
                    await asyncio.to_thread(settings_db.delete, key)
                await event.reply(t("threshold_reset"), parse_mode=None)
                return
            if len(parts) != 2 or parts[0] not in names:
                raise ValueError(t("threshold_usage"))
            key = names[parts[0]]
            value = runtime.set_value(key, parts[1])
            await asyncio.to_thread(settings_db.save, key, value)
            await event.reply(f"✅ {parts[0]} = {value}", parse_mode=None)
        except ValueError as exc:
            await event.reply(f"❌ {exc}", parse_mode=None)
        except Exception:
            await event.reply(t("threshold_save_failed"), parse_mode=None)

    # --- /mute, /unmute ---
    @client.on(events.NewMessage(from_users=[owner_id], pattern=r"^/mute(?:\s+(.+))?$"))
    async def mute(event):
        word = (event.pattern_match.group(1) or "").strip()
        if not word:
            words = await asyncio.to_thread(mute_words.list_words)
            text = t("mute_list", count=len(words), words="\n".join(f"• {w}" for w in words)) if words else t("mute_empty")
            await event.reply(text, parse_mode=None)
            return
        outcome = await asyncio.to_thread(mute_words.add, word)
        if outcome == "added" and on_channels_changed:
            await on_channels_changed(force=True)
        key = {"added": "mute_added", "exists": "mute_exists", "limit": "mute_limit", "invalid": "mute_invalid"}[outcome]
        await event.reply(
            t(key, word=word, limit=config.MUTE_WORDS_LIMIT, min=config.MUTE_WORD_MIN, max=config.MUTE_WORD_MAX),
            parse_mode=None,
        )

    @client.on(events.NewMessage(from_users=[owner_id], pattern=r"^/unmute(?:\s+(.+))?$"))
    async def unmute(event):
        word = (event.pattern_match.group(1) or "").strip()
        if not word:
            await event.reply(t("mute_empty"), parse_mode=None)
            return
        if await asyncio.to_thread(mute_words.remove, word):
            if on_channels_changed:
                await on_channels_changed(force=True)
            await event.reply(t("mute_removed", word=word), parse_mode=None)
        else:
            await event.reply(t("mute_not_found", word=word), parse_mode=None)

    # --- /mode, /digest, /quiet, /tz ---
    async def change_setting(event, name, raw, ok_text):
        """Validate, apply and persist one runtime setting; reply with ok_text(value) or the validation error."""
        try:
            value = runtime.set_value(name, raw)
        except ValueError as exc:
            await event.reply(f"❌ {exc}", parse_mode=None)
            return
        await asyncio.to_thread(settings_db.save, name, value)
        await event.reply(ok_text(value), parse_mode=None)

    @client.on(events.NewMessage(from_users=[owner_id], pattern=r"^/mode(?:\s+(\S+))?$"))
    async def delivery_mode(event):
        choice = event.pattern_match.group(1)
        if not choice:
            await event.reply(
                t("mode_show", mode=runtime.get("delivery_mode"), hours=runtime.get("digest_hours")),
                parse_mode=None,
            )
            return
        await change_setting(event, "delivery_mode", choice, lambda value: t("mode_set", mode=value))

    @client.on(events.NewMessage(from_users=[owner_id], pattern=r"^/digest(?:\s+(\S+))?$"))
    async def digest(event):
        arg = event.pattern_match.group(1)
        if not arg:
            queued = await asyncio.to_thread(digest_db.count_unsent)
            await event.reply(t("digest_show", hours=runtime.get("digest_hours"), queued=queued), parse_mode=None)
            return
        if arg.lower() == "now":
            sent = await flush_digest() if flush_digest else 0
            await event.reply(t("digest_sent", count=sent) if sent else t("digest_empty"), parse_mode=None)
            return
        await change_setting(event, "digest_hours", arg, lambda value: t("digest_set", hours=value))

    @client.on(events.NewMessage(from_users=[owner_id], pattern=r"^/quiet(?:\s+(.+))?$"))
    async def quiet_hours(event):
        arg = (event.pattern_match.group(1) or "").strip()
        zone_name = runtime.get("timezone")
        if not arg:
            window = runtime.get("quiet_hours")
            text = t("quiet_show", window=window, zone=zone_name) if window else t("quiet_off_show")
            await event.reply(text, parse_mode=None)
            return
        await change_setting(
            event, "quiet_hours", arg,
            lambda value: t("quiet_set", window=value, zone=zone_name) if value else t("quiet_cleared"),
        )

    @client.on(events.NewMessage(from_users=[owner_id], pattern=r"^/tz(?:\s+(\S+))?$"))
    async def timezone_command(event):
        arg = event.pattern_match.group(1)
        if not arg:
            await event.reply(t("tz_show", zone=runtime.get("timezone")), parse_mode=None)
            return
        await change_setting(event, "timezone", arg, lambda value: t("tz_set", zone=value))

    # --- /lang ---
    @client.on(events.NewMessage(from_users=[owner_id], pattern=r"^/lang(?:\s+(\S+))?$"))
    async def language(event):
        choice = event.pattern_match.group(1)
        if not choice:
            await event.reply(t("lang_usage", language=i18n.get_language()), parse_mode=None)
            return
        try:
            value = runtime.set_value("language", choice)
            await asyncio.to_thread(settings_db.save, "language", value)
            await event.reply(t("lang_set", language=value), parse_mode=None)
        except ValueError as exc:
            await event.reply(f"❌ {exc}", parse_mode=None)

    async def resolve_pending(event, parts):
        usage = t("pending_resolve_usage")
        if len(parts) != 2 or not parts[0].isdigit() or parts[1] not in publications.RESOLUTIONS:
            await event.reply(usage, parse_mode=None)
            return
        claim_id, outcome = int(parts[0]), parts[1]
        try:
            resolved = await asyncio.to_thread(publications.resolve_pending, claim_id, outcome)
        except Exception:
            await event.reply(t("pending_resolve_failed"), parse_mode=None)
            raise
        if not resolved:
            await event.reply(t("pending_not_found"), parse_mode=None)
            return
        meaning = t("pending_meaning_sent") if outcome == "sent" else t("pending_meaning_failed")
        await event.reply(t("pending_resolved", id=claim_id, meaning=meaning), parse_mode=None)

    @client.on(events.NewMessage(from_users=[owner_id], pattern=r"^/pending(?:\s+(.+))?$"))
    async def pending(event):
        arg = (event.pattern_match.group(1) or "").strip()
        page = 1
        parts = arg.split()
        if parts and parts[0] == "resolve":
            await resolve_pending(event, parts[1:])
            return
        if parts and parts[0] == "page":
            if len(parts) != 2 or not parts[1].isdigit() or int(parts[1]) < 1:
                await event.reply(t("pending_usage"))
                return
            page = int(parts[1])
            arg = ""
        elif arg and not arg.isdigit():
            await event.reply(t("pending_usage"))
            return
        try:
            if arg:
                row = await asyncio.to_thread(publications.get_pending, int(arg))
                if not row:
                    await event.reply(t("pending_not_found"))
                    return
                rows = [row]
            else:
                rows = await asyncio.to_thread(publications.list_pending, 11, (page - 1) * 10)

            if not rows:
                await event.reply(t("pending_empty"))
                return

            lines = [t("pending_header")]
            for row in rows[:10]:
                label = row["title"] or row["username"] or row["channel_id"]
                link = source_link(row["username"], row["channel_id"], row["message_id"])
                lines.append(
                    f"#{row['id']} | {label} | {row['created_at']} | "
                    f"cluster={row['cluster_id']}"
                )
                lines.append(link or t("pending_source", channel=row["channel_id"], message=row["message_id"]))
            if len(rows) > 10:
                lines.append(t("pending_next_page", page=page + 1))
            lines.append(t("pending_footer"))
            await event.reply("\n".join(lines), parse_mode=None)
        except Exception:
            await event.reply(t("pending_list_error"))

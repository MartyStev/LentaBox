"""Management of tracked channels based on the account's own subscriptions."""

import asyncio
import logging
import math
import re

from telethon import events

import config
from db import channels
import db.settings as settings_db
from core import runtime
from core.i18n import t
from core import subscriptions as subs

log = logging.getLogger("stenabot.subscriptions")
PAGE_RE = re.compile(r"(?:^|\s)(?:page|стр)\s+(\d+)\s*$", re.IGNORECASE)
FOLDER_RE = re.compile(r"^(?:folder|папка)\s+(.+)$", re.IGNORECASE)
SHOWN_NAMES = 15


def _names(items) -> str:
    labels = [item.label for item in items[:SHOWN_NAMES]]
    extra = len(items) - SHOWN_NAMES
    return ", ".join(labels) + (t("names_more", extra=extra) if extra > 0 else "")


async def apply_sync(fetch_subs):
    """Add new subscriptions and drop channels the account has left."""
    current = await fetch_subs()
    tracked = await asyncio.to_thread(channels.list_channels)
    excluded = await asyncio.to_thread(channels.list_exclusions)
    plan = subs.guard_removals(subs.plan_sync(current, tracked, excluded), current, tracked)
    for item in plan.to_add:
        await asyncio.to_thread(
            channels.add_channel, item.telegram_id, item.username, item.title, "sync",
        )
    for telegram_id in plan.to_remove:
        await asyncio.to_thread(channels.remove_channel, telegram_id)
    removed = [row for row in tracked if row["telegram_id"] in set(plan.to_remove)]
    return plan, removed


class SubscriptionManager:
    def __init__(self, fetch_subs, fetch_folders, on_changed=None):
        self._fetch_subs = fetch_subs
        self._fetch_folders = fetch_folders
        self._on_changed = on_changed
        self.listing: list = []

    async def _changed(self):
        if self._on_changed:
            await self._on_changed(force=True)

    async def _tracked_ids(self) -> set:
        rows = await asyncio.to_thread(channels.list_channels)
        return {row["telegram_id"] for row in rows}

    async def _resolve_folder(self, name: str):
        folders = await self._fetch_folders()
        title, folder = subs.find_folder(folders, name)
        if folder is None:
            known = ", ".join(folders) or t("folder_none")
            raise ValueError(t("folder_not_found", name=name, known=known))
        return title, folder

    async def _select(self, query: str):
        """Subscriptions matching the filter, plus a label for it."""
        current = await self._fetch_subs()
        folder_match = FOLDER_RE.match(query)
        if folder_match:
            title, folder = await self._resolve_folder(folder_match.group(1))
            return subs.folder_members(folder, current), t("scope_folder", title=title)
        tracked = await self._tracked_ids()
        label = t("scope_filter", query=query) if query else t("scope_all")
        return subs.apply_filter(current, tracked, query), label

    async def show(self, args: str) -> str:
        page = 1
        page_match = PAGE_RE.search(args)
        if page_match:
            page = int(page_match.group(1))
            args = args[:page_match.start()].strip()
        query = args.strip()

        items, label = await self._select(query)
        self.listing = items
        tracked = await self._tracked_ids()
        if not items:
            return t("subs_nothing", label=label)

        size = config.SUBS_PAGE_SIZE
        pages = math.ceil(len(items) / size)
        if not 1 <= page <= pages:
            raise ValueError(t("subs_no_page", page=page, pages=pages))

        lines = [
            t("subs_header", label=label, count=len(items),
              tracked=sum(i.telegram_id in tracked for i in items), page=page, pages=pages)
        ]
        for number, item in enumerate(items[(page - 1) * size:page * size],
                                      start=(page - 1) * size + 1):
            mark = "✅" if item.telegram_id in tracked else "⬜"
            name = f"{item.label} — {item.title}" if item.username and item.title != item.username else item.label
            lines.append(f"{number}. {mark} {name}{' 📦' if item.archived else ''}")
        if page < pages:
            lines.append(t("subs_next", query=query, page=page + 1).replace("  ", " "))
        lines.append(t("subs_footer"))
        return "\n".join(lines)

    async def _targets(self, args: str):
        args = args.strip()
        folder_match = FOLDER_RE.match(args)
        if folder_match:
            title, folder = await self._resolve_folder(folder_match.group(1))
            self.listing = subs.folder_members(folder, await self._fetch_subs())
            return self.listing, t("scope_folder", title=title)
        if args.lower() in {"all", "все"}:
            if not self.listing:
                self.listing = await self._fetch_subs()
            return self.listing, t("scope_last")
        if not self.listing:
            raise ValueError(t("track_first"))
        numbers = subs.parse_selection(args, len(self.listing))
        return [self.listing[n - 1] for n in numbers], t("scope_selection")

    async def track(self, args: str) -> str:
        if not args.strip():
            raise ValueError(t("track_usage"))
        targets, scope = await self._targets(args)
        tracked = await self._tracked_ids()
        added = [item for item in targets if item.telegram_id not in tracked]
        for item in added:
            await asyncio.to_thread(
                channels.add_channel, item.telegram_id, item.username, item.title, "sync",
            )
            await asyncio.to_thread(channels.clear_exclusion, item.telegram_id)
        await self._changed()
        if not added:
            return t("track_already", scope=scope)
        return t("track_done", scope=scope, count=len(added), names=_names(added))

    async def untrack(self, args: str) -> str:
        if not args.strip():
            raise ValueError(t("untrack_usage"))
        targets, scope = await self._targets(args)
        tracked = await self._tracked_ids()
        removed = [item for item in targets if item.telegram_id in tracked]
        for item in removed:
            await asyncio.to_thread(channels.remove_channel, item.telegram_id)
            await asyncio.to_thread(channels.add_exclusion, item.telegram_id)
        await self._changed()
        if not removed:
            return t("untrack_none", scope=scope)
        return t("untrack_done", scope=scope, count=len(removed), names=_names(removed))

    async def folders(self) -> str:
        folders = await self._fetch_folders()
        if not folders:
            return t("folders_none")
        current = await self._fetch_subs()
        tracked = await self._tracked_ids()
        lines = [t("folders_header")]
        for title, folder in folders.items():
            members = subs.folder_members(folder, current)
            new = sum(m.telegram_id not in tracked for m in members)
            lines.append(t("folders_item", title=title, count=len(members), new=new))
        lines.append(t("folders_footer"))
        return "\n".join(lines)

    async def sync(self, args: str) -> str:
        if args.strip().lower() == "apply":
            plan, removed = await apply_sync(self._fetch_subs)
            await self._changed()
            return self._sync_report(t("sync_done_title"), plan, removed)

        current = await self._fetch_subs()
        tracked = await asyncio.to_thread(channels.list_channels)
        excluded = await asyncio.to_thread(channels.list_exclusions)
        plan = subs.guard_removals(subs.plan_sync(current, tracked, excluded), current, tracked)
        removed = [row for row in tracked if row["telegram_id"] in set(plan.to_remove)]
        if not plan.to_add and not removed:
            return t("sync_nothing")
        return self._sync_report(t("sync_pending_title"), plan, removed) + "\n" + t("sync_apply_hint")

    @staticmethod
    def _sync_report(title, plan, removed) -> str:
        lines = [f"{title}:"]
        lines.append(t("sync_added", count=len(plan.to_add))
                     + (f"\n{_names(plan.to_add)}" if plan.to_add else ""))
        removed_labels = [row.get("title") or str(row["telegram_id"]) for row in removed]
        lines.append(t("sync_removed", count=len(removed))
                     + (f"\n{', '.join(removed_labels[:SHOWN_NAMES])}" if removed else ""))
        return "\n".join(lines)

    async def autosync(self, args: str) -> str:
        args = args.strip()
        if not args:
            state = t("autosync_on_word") if runtime.get("autosync") else t("autosync_off_word")
            return t("autosync_show", state=state, minutes=config.AUTOSYNC_INTERVAL_SEC // 60)
        value = runtime.parse("autosync", args)
        await asyncio.to_thread(settings_db.save, "autosync", "on" if value else "off")
        runtime.set_value("autosync", "on" if value else "off")
        if not value:
            return t("autosync_off")
        plan, removed = await apply_sync(self._fetch_subs)
        await self._changed()
        return self._sync_report(t("autosync_enabled_title"), plan, removed)


def register_subscription_commands(client, owner_id, on_channels_changed=None):
    manager = SubscriptionManager(
        fetch_subs=lambda: subs.fetch_subscriptions(client),
        fetch_folders=lambda: subs.fetch_folders(client),
        on_changed=on_channels_changed,
    )

    def command(name, method, takes_args=True):
        pattern = rf"^/{name}(?:\s+(.+))?$" if takes_args else rf"^/{name}$"

        @client.on(events.NewMessage(from_users=[owner_id], pattern=pattern))
        async def handler(event):
            args = (event.pattern_match.group(1) or "") if takes_args else ""
            try:
                text = await (method(args) if takes_args else method())
            except ValueError as exc:
                text = f"❌ {exc}"
            except Exception:
                log.exception("Command /%s failed", name)
                text = t("command_failed", name=name)
            await event.reply(text, parse_mode=None)

        return handler

    command("subs", manager.show)
    command("track", manager.track)
    command("untrack", manager.untrack)
    command("sync", manager.sync)
    command("autosync", manager.autosync)
    command("folders", manager.folders, takes_args=False)
    return manager

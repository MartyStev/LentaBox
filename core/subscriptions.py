"""The account's own subscriptions: channel list, folders, selection and sync plan."""

import logging
import re
from dataclasses import dataclass

from telethon.tl import functions
from telethon.utils import get_peer_id

from core.i18n import t

log = logging.getLogger("stenabot.subscriptions")

NEW_ALIASES = {"new", "новые", "новое"}
TRACKED_ALIASES = {"tracked", "подключённые", "подключенные", "мои"}
RANGE_RE = re.compile(r"^(\d+)(?:-(\d+))?$")


@dataclass(frozen=True)
class Sub:
    telegram_id: int
    username: str | None
    title: str
    archived: bool = False

    @property
    def label(self) -> str:
        return f"@{self.username}" if self.username else self.title


@dataclass(frozen=True)
class SyncPlan:
    to_add: list
    to_remove: list


def parse_selection(text: str, size: int) -> list[int]:
    """Parse '1 3 5-7' into a list of numbers (1..size) without duplicates."""
    tokens = [token for token in re.split(r"[\s,]+", text.strip()) if token]
    if not tokens:
        raise ValueError(t("sel_empty"))
    numbers: list[int] = []
    for token in tokens:
        match = RANGE_RE.match(token)
        if not match:
            raise ValueError(t("sel_bad_number", token=token))
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if start < 1 or end > size or start > end:
            raise ValueError(t("sel_out_of_range", size=size, token=token))
        numbers.extend(n for n in range(start, end + 1) if n not in numbers)
    return numbers


def apply_filter(items, tracked_ids, query: str):
    """Filter subscriptions: all / new / tracked / search by title."""
    query = query.strip().casefold()
    if not query:
        return list(items)
    if query in NEW_ALIASES:
        return [s for s in items if s.telegram_id not in tracked_ids]
    if query in TRACKED_ALIASES:
        return [s for s in items if s.telegram_id in tracked_ids]
    return [
        s for s in items
        if query in s.title.casefold() or query in (s.username or "").casefold()
    ]


def plan_sync(current, tracked_rows, excluded) -> SyncPlan:
    """What to add from subscriptions and what to remove from previously synced channels."""
    tracked_ids = {row["telegram_id"] for row in tracked_rows}
    current_ids = {s.telegram_id for s in current}
    to_add = [
        s for s in current
        if s.telegram_id not in tracked_ids and s.telegram_id not in excluded
    ]
    to_remove = [
        row["telegram_id"] for row in tracked_rows
        if row.get("source") == "sync" and row["telegram_id"] not in current_ids
    ]
    return SyncPlan(to_add=to_add, to_remove=to_remove)


def guard_removals(plan: SyncPlan, current, tracked_rows, max_share: float = 0.3) -> SyncPlan:
    """Do not remove channels based on incomplete data.

    An empty get_dialogs() response, or a sudden disappearance of a large share of
    subscriptions, more often means a session failure than a mass unsubscribe.
    """
    if not plan.to_remove:
        return plan
    synced = [row for row in tracked_rows if row.get("source") == "sync"]
    if not current or len(plan.to_remove) > max(3, max_share * len(synced)):
        log.warning("Auto-removal of %s channels cancelled: suspiciously many", len(plan.to_remove))
        return SyncPlan(to_add=plan.to_add, to_remove=[])
    return plan


def folder_members(folder: dict, current):
    """Subscriptions that belong to a Telegram folder."""
    return [
        s for s in current
        if s.telegram_id not in folder["exclude"]
        and (s.telegram_id in folder["include"] or folder["broadcasts"])
    ]


def find_folder(folders: dict, name: str):
    """Find a folder by title: exact match first, then a single partial match."""
    wanted = name.strip().casefold()
    for title, folder in folders.items():
        if title.casefold() == wanted:
            return title, folder
    partial = [(title, folder) for title, folder in folders.items() if wanted in title.casefold()]
    return partial[0] if len(partial) == 1 else (None, None)


async def fetch_subscriptions(client) -> list[Sub]:
    """All channels (not groups) the account is subscribed to, including the archive."""
    result = []
    for dialog in await client.get_dialogs():
        entity = dialog.entity
        if not getattr(entity, "broadcast", False) or getattr(entity, "left", False):
            continue
        result.append(Sub(
            telegram_id=get_peer_id(entity),
            username=getattr(entity, "username", None),
            title=getattr(entity, "title", None) or str(entity.id),
            archived=bool(getattr(dialog, "archived", False)),
        ))
    return sorted(result, key=lambda s: s.title.casefold())


def _peer_ids(peers) -> set[int]:
    ids = set()
    for peer in peers or []:
        try:
            ids.add(get_peer_id(peer))
        except Exception:
            log.debug("Skipped unrecognized folder peer: %r", peer)
    return ids


async def fetch_folders(client) -> dict[str, dict]:
    """Chat folders of the account: {title: {include, exclude, broadcasts}}."""
    result = await client(functions.messages.GetDialogFiltersRequest())
    folders = {}
    for item in getattr(result, "filters", result):
        if not hasattr(item, "include_peers"):
            continue
        title = getattr(item.title, "text", item.title)
        folders[str(title)] = {
            "include": _peer_ids(list(item.include_peers) + list(getattr(item, "pinned_peers", []))),
            "exclude": _peer_ids(getattr(item, "exclude_peers", [])),
            "broadcasts": bool(getattr(item, "broadcasts", False)),
        }
    return folders

"""Parsing of user channel input: @name, t.me link, invite link."""

import re
from dataclasses import dataclass

USERNAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$", re.ASCII)
LINK_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me|telegram\.dog)/"
    r"(?:(?P<invite>\+[A-Za-z0-9_-]{8,})|joinchat/(?P<invite2>[A-Za-z0-9_-]{8,})|(?P<name>[A-Za-z][A-Za-z0-9_]{3,31}))"
    r"(?:/\d+)?/?(?:\?.*)?$",
    re.IGNORECASE | re.ASCII,   # without ASCII, case-insensitivity also matches U+212A (Kelvin sign) and U+017F
)


@dataclass(frozen=True)
class ChannelRef:
    kind: str    # username | invite
    value: str   # name without @, or invite hash without +


def parse_channel_ref(text: str) -> ChannelRef | None:
    text = (text or "").strip()
    if not text or not text.isascii():
        return None
    if text.startswith("@"):
        name = text[1:]
        return ChannelRef("username", name.lower()) if USERNAME_RE.match(name) else None
    match = LINK_RE.match(text)
    if match:
        invite = match.group("invite") or match.group("invite2")
        if invite:
            return ChannelRef("invite", invite.lstrip("+"))
        return ChannelRef("username", match.group("name").lower())
    if USERNAME_RE.match(text):
        return ChannelRef("username", text.lower())
    return None

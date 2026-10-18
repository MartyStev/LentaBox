"""Quiet hours: a daily window in the owner's timezone during which nothing is posted right away."""

import re
from datetime import UTC, datetime, time, tzinfo

WINDOW_RE = re.compile(r"^(\d{2}):(\d{2})-(\d{2}):(\d{2})$")

Window = tuple[time, time]


def parse_window_strict(text: str) -> Window | None:
    """``"23:00-08:00"`` -> (23:00, 08:00); ``""`` or ``"off"`` -> None; anything else raises ValueError."""
    text = (text or "").strip()
    if text == "" or text.lower() == "off":
        return None
    match = WINDOW_RE.match(text)
    if not match:
        raise ValueError("Expected HH:MM-HH:MM, for example 23:00-08:00, or off")
    start_h, start_m, end_h, end_m = (int(g) for g in match.groups())
    if start_h > 23 or end_h > 23 or start_m > 59 or end_m > 59:
        raise ValueError("Hours must be 00-23 and minutes 00-59")
    start, end = time(start_h, start_m), time(end_h, end_m)
    if start == end:
        raise ValueError("Start and end must differ")
    return start, end


def parse_window(text: str) -> Window | None:
    """Lenient variant for stored values: a corrupt value means "no quiet hours"."""
    try:
        return parse_window_strict(text)
    except ValueError:
        return None


def format_window(window: Window | None) -> str:
    if window is None:
        return ""
    return f"{window[0]:%H:%M}-{window[1]:%H:%M}"


def in_quiet(now: datetime, window: Window | None, zone: tzinfo) -> bool:
    """Is ``now`` inside the window? The end is exclusive; windows that cross midnight are supported."""
    if window is None:
        return False
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    local = now.astimezone(zone).time().replace(second=0, microsecond=0)
    start, end = window
    if start < end:
        return start <= local < end
    return local >= start or local < end

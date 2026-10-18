"""Digest text: one line per story with a link, split into messages that fit Telegram's limit."""

import html

from core.i18n import t

HEADLINE_LIMIT = 120
MESSAGE_LIMIT = 4000        # below Telegram's 4096


def _utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def headline(text: str, limit: int = HEADLINE_LIMIT) -> str:
    """First non-empty line of the post, cut to ``limit`` characters."""
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if line:
            return line if len(line) <= limit else line[: limit - 1].rstrip() + "…"
    return "…"


def format_digest(rows: list[dict], lang: str | None = None) -> list[str]:
    """Rows are dicts with ``headline``, ``channel_label`` and ``link`` (may be empty)."""
    header = t("digest_header", lang=lang, count=len(rows))
    link_word = t("digest_link", lang=lang)
    messages: list[str] = []
    current = header
    for row in rows:
        line = f"• {html.escape(row['headline'])} — {html.escape(row['channel_label'])}"
        if row.get("link"):
            line += f' · <a href="{html.escape(row["link"], quote=True)}">{link_word}</a>'
        if _utf16_len(current) + _utf16_len(line) + 1 > MESSAGE_LIMIT:
            messages.append(current)
            current = ""
        current += ("\n" if current else "") + line
    messages.append(current)
    return messages

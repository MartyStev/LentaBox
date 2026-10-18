"""Cleans news text before comparison and embedding.

Channel signatures, links, hashtags and emoji do not describe the event, but they make
different news items from the same channel look highly similar. They are stripped here.
"""

import re
import unicodedata
from functools import lru_cache

URL_RE = re.compile(r"(?:https?://|www\.|t\.me/)\S+", re.IGNORECASE)
MENTION_RE = re.compile(r"@\w+")
HASHTAG_RE = re.compile(r"#\w+")
SPACES_RE = re.compile(r"[ \t ]+")

# Symbols from categories S* and C* that carry meaning in news.
KEEP_SYMBOLS = set("$€₽£¥+°№=≈~")

# Channel boilerplate lines: calls to subscribe, submit a news tip, etc.
PROMO_LINE_RE = re.compile(
    r"подпис(?:аться|ывайтесь|ывайся|ывайтесь|ись|ка на)"
    r"|(?:прислать|предложить|отправить)\s+новост"
    r"|\b(?:наш|наши)\s+(?:канал|чат)\b"
    r"|\bмы\s+в\s+(?:telegram|телеграм|max|макс|дзен)\b"
    r"|\bчитайте\s+нас\b|\bприсоединяйтесь\s+к\b"
    r"|\bsubscribe\b|\bfollow\s+us\b|\bjoin\s+(?:us|our|the\s+channel)\b"
    r"|\bour\s+(?:channel|chat)\b|\bshare\s+this\b",
    re.IGNORECASE,
)
PROMO_LINE_MAX = 80

AD_RE = re.compile(
    r"\berid\b|#реклама|#промо\b|на\s+правах\s+рекламы"
    r"|\bпромокод\w*|партн[её]рск\w+\s+(?:материал|публикаци)"
    r"|#ad\b|#sponsored\b|\bsponsored\s+(?:by|post|content)\b|\bpaid\s+partnership\b"
    r"|\bpromo\s*code\b|\baffiliate\s+link\b",
    re.IGNORECASE,
)


def _strip_symbols(line: str) -> str:
    return "".join(
        ch for ch in line
        if ch in KEEP_SYMBOLS or unicodedata.category(ch)[0] not in "SC"
    )


def _clean_line(line: str) -> str:
    line = URL_RE.sub(" ", line)
    line = MENTION_RE.sub(" ", line)
    line = HASHTAG_RE.sub(" ", line)
    return SPACES_RE.sub(" ", _strip_symbols(line)).strip()


def clean_text(text: str) -> str:
    """Event text without links, mentions, hashtags, emoji and channel calls to action."""
    lines = [_clean_line(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    content = [
        line for line in lines
        if not (len(line) <= PROMO_LINE_MAX and PROMO_LINE_RE.search(line))
    ]
    return " ".join(content or lines)


@lru_cache(maxsize=4096)
def matching_text(text: str, limit: int) -> str:
    """Normalized beginning of the cleaned text, for fuzzy comparison and embeddings."""
    return re.sub(r"\s+", " ", clean_text(text).lower()).strip()[:limit]


def is_ad(text: str) -> bool:
    return bool(AD_RE.search(text))

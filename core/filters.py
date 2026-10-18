"""Owner's muted words: a post whose text contains one of them is not published."""

import config


def normalize_word(word: str | None) -> str | None:
    """Lower-cased word with single spaces, or None if it is empty, too short or too long."""
    word = " ".join((word or "").lower().split())
    if not (config.MUTE_WORD_MIN <= len(word) <= config.MUTE_WORD_MAX):
        return None
    return word


def matches(text: str | None, words) -> bool:
    """True if the text contains at least one muted word (case-insensitive substring)."""
    lowered = (text or "").lower()
    return any(w and w in lowered for w in (words or ()))

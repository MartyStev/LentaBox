import config
from core.filters import normalize_word
from db.connection import execute


def add(word: str) -> str:
    """added | exists | limit | invalid."""
    word = normalize_word(word)
    if word is None:
        return "invalid"
    rows = execute(
        """
        INSERT INTO mute_words (word)
        SELECT %s WHERE (SELECT COUNT(*) FROM mute_words) < %s
        ON CONFLICT DO NOTHING
        RETURNING word
        """,
        (word, config.MUTE_WORDS_LIMIT),
        fetch=True,
        retry=False,
    )
    if rows:
        return "added"
    present = execute("SELECT 1 FROM mute_words WHERE word = %s", (word,), fetch=True)
    return "exists" if present else "limit"


def remove(word: str) -> bool:
    word = normalize_word(word)
    if word is None:
        return False
    rows = execute("DELETE FROM mute_words WHERE word = %s RETURNING word", (word,), fetch=True)
    return bool(rows)


def list_words() -> list[str]:
    rows = execute("SELECT word FROM mute_words ORDER BY word", fetch=True)
    return [row["word"] for row in rows or []]

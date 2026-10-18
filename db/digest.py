"""Queue of stories waiting for a digest message."""

from db.connection import execute


def list_unsent(limit: int = 300) -> list[dict]:
    return execute(
        """
        SELECT id, cluster_id, channel_id, message_id, headline, link, channel_label, created_at
        FROM digest_queue
        WHERE sent_at IS NULL
        ORDER BY created_at, id
        LIMIT %s
        """,
        (limit,),
        fetch=True,
    ) or []


def count_unsent() -> int:
    return execute("SELECT COUNT(*) AS n FROM digest_queue WHERE sent_at IS NULL", fetch=True)[0]["n"]


def mark_sent(ids: list[int]) -> int:
    """Mark rows as sent after the digest reached the chat; returns how many rows changed."""
    if not ids:
        return 0
    rows = execute(
        "UPDATE digest_queue SET sent_at = NOW() WHERE id = ANY(%s) AND sent_at IS NULL RETURNING id",
        (list(ids),),
        fetch=True,
    )
    return len(rows or [])


def last_sent_at():
    rows = execute("SELECT MAX(sent_at) AS last FROM digest_queue", fetch=True)
    return rows[0]["last"] if rows else None


def purge_sent(days: int) -> int:
    rows = execute(
        "DELETE FROM digest_queue WHERE sent_at IS NOT NULL AND sent_at < NOW() - (%s * INTERVAL '1 day') RETURNING id",
        (days,),
        fetch=True,
    )
    return len(rows or [])

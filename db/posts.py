from db.connection import execute


def post_exists(text_hash, limit=500):
    """
    Protection against exact copy-paste
    (the same text has already been sent)
    """
    rows = execute(
        """
        SELECT 1
        FROM (
            SELECT text_hash
            FROM posts
            WHERE text_hash IS NOT NULL
            ORDER BY saved_at DESC
            LIMIT %s
        ) AS recent
        WHERE recent.text_hash = %s
        LIMIT 1
        """,
        (limit, text_hash),
        fetch=True
    )
    return bool(rows)


def get_recent_texts(limit=300):
    """
    Texts of already sent posts for fuzzy dedup.
    """
    rows = execute(
        """
        SELECT text_content
        FROM posts
        WHERE text_content IS NOT NULL
          AND text_content <> ''
        ORDER BY saved_at DESC
        LIMIT %s
        """,
        (limit,),
        fetch=True
    )
    return [r["text_content"] for r in rows] if rows else []


def origin_seen(origin_key):
    """This post (or its original, if it is a repost) has already been published."""
    rows = execute(
        "SELECT 1 FROM posts WHERE origin_key = %s LIMIT 1",
        (origin_key,),
        fetch=True,
    )
    return bool(rows)


def last_saved_at():
    rows = execute("SELECT MAX(saved_at) AS last FROM posts", fetch=True)
    return rows[0]["last"] if rows else None

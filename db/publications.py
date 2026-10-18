"""Reserve a cluster before sending, then persist the result atomically."""

import config
from db.connection import execute, get_connection


def list_pending(limit=10, offset=0):
    return execute(
        """
        SELECT p.id, p.cluster_id, p.channel_id, p.message_id, p.created_at,
               c.username, c.title
        FROM publication_claims AS p
        LEFT JOIN channels AS c ON c.telegram_id::text = p.channel_id
        WHERE p.state = 'pending'
        ORDER BY p.created_at ASC
        LIMIT %s OFFSET %s
        """,
        (limit, offset),
        fetch=True,
    ) or []


def get_pending(claim_id):
    rows = execute(
        """
        SELECT p.id, p.cluster_id, p.channel_id, p.message_id, p.created_at,
               c.username, c.title
        FROM publication_claims AS p
        LEFT JOIN channels AS c ON c.telegram_id::text = p.channel_id
        WHERE p.id = %s AND p.state = 'pending'
        """,
        (claim_id,),
        fetch=True,
    )
    return rows[0] if rows else None


def has_pending_conflict(cluster_id, channel_id, message_id):
    rows = execute(
        """
        SELECT 1 FROM publication_claims
        WHERE state = 'pending'
          AND ((cluster_id = %s AND created_at > NOW() - (%s * INTERVAL '1 hour'))
               OR (channel_id = %s AND message_id = %s))
        LIMIT 1
        """,
        (cluster_id, config.CLUSTER_WINDOW_HOURS, str(channel_id), message_id),
        fetch=True,
    )
    return bool(rows)


def claim(cluster_id, channel_id, message_id):
    """Return a claim ID, or None if this story was sent or claimed within the window."""
    rows = execute(
        """
        INSERT INTO publication_claims (cluster_id, channel_id, message_id)
        SELECT %s, %s, %s
        WHERE NOT EXISTS (
            SELECT 1 FROM news_clusters
            WHERE id = %s AND last_sent_at > NOW() - (%s * INTERVAL '1 hour')
        )
        AND NOT EXISTS (
            SELECT 1 FROM publication_claims
            WHERE cluster_id = %s AND created_at > NOW() - (%s * INTERVAL '1 hour')
        )
        ON CONFLICT DO NOTHING
        RETURNING id
        """,
        (cluster_id, str(channel_id), message_id,
         cluster_id, config.CLUSTER_WINDOW_HOURS,
         cluster_id, config.CLUSTER_WINDOW_HOURS),
        fetch=True,
        retry=False,
    )
    return rows[0]["id"] if rows else None


def finalize(claim_id, cluster_id, channel_id, message_id, text_hash, text,
             origin_key=None, queue_entry=None):
    """Persist the sent post, cluster timestamp and claim in one transaction.

    ``queue_entry`` ({headline, link, channel_label}) is for stories deferred to a digest: the queue row
    is written in the same transaction, so a story is never "published" without being queued or vice versa.
    """
    conn = get_connection()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO posts (
                    channel_id, telegram_message_id, text_hash, text_content, cluster_id,
                    origin_key
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (channel_id, message_id, text_hash, text, cluster_id, origin_key),
            )
            cur.execute(
                "UPDATE news_clusters SET last_sent_at = NOW() WHERE id = %s",
                (cluster_id,),
            )
            cur.execute(
                """
                UPDATE publication_claims
                SET state = 'sent', sent_at = NOW()
                WHERE id = %s AND state = 'pending'
                """,
                (claim_id,),
            )
            if cur.rowcount != 1:
                raise RuntimeError(f"Publication claim {claim_id} is not pending")
            if queue_entry is not None:
                cur.execute(
                    """
                    INSERT INTO digest_queue (cluster_id, channel_id, message_id, headline, link, channel_label)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (cluster_id, str(channel_id), message_id, queue_entry["headline"],
                     queue_entry.get("link"), queue_entry["channel_label"]),
                )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def release(claim_id):
    """Drop a pending claim after Telegram rejected the send: nothing was published."""
    execute(
        "DELETE FROM publication_claims WHERE id = %s AND state = 'pending'",
        (claim_id,),
    )


RESOLUTIONS = {"sent", "failed"}


def resolve_pending(claim_id, outcome):
    """Close a reservation with an uncertain outcome based on a manual check.

    sent   - the publication exists in the target chat: the reservation counts as sent,
             there will be no resend, and the channel cursor moves on.
    failed - there is no publication: the reservation is deleted, and the next pass retries sending.
    Returns False if the reservation is not found or is already closed.
    """
    if outcome not in RESOLUTIONS:
        raise ValueError(f"Unknown outcome: {outcome}")
    conn = get_connection()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            if outcome == "failed":
                cur.execute(
                    "DELETE FROM publication_claims WHERE id = %s AND state = 'pending'",
                    (claim_id,),
                )
                resolved = cur.rowcount == 1
            else:
                cur.execute(
                    """
                    UPDATE publication_claims
                    SET state = 'sent', sent_at = NOW()
                    WHERE id = %s AND state = 'pending'
                    RETURNING cluster_id
                    """,
                    (claim_id,),
                )
                row = cur.fetchone()
                resolved = row is not None
                if resolved:
                    cur.execute(
                        "UPDATE news_clusters SET last_sent_at = NOW() WHERE id = %s",
                        (row[0],),
                    )
        conn.commit()
        return resolved
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def expire_pending(hours):
    """Close pending reservations older than hours hours; return the closed rows.

    State expired: the publication is unconfirmed and will not be retried,
    and the channel cursor moves on at the next pass.
    """
    return execute(
        """
        WITH expired AS (
            UPDATE publication_claims
            SET state = 'expired'
            WHERE state = 'pending' AND created_at < NOW() - (%s * INTERVAL '1 hour')
            RETURNING id, cluster_id, channel_id, message_id, created_at
        )
        SELECT e.id, e.cluster_id, e.channel_id, e.message_id, e.created_at,
               c.username, c.title
        FROM expired AS e
        LEFT JOIN channels AS c ON c.telegram_id::text = e.channel_id
        ORDER BY e.created_at
        """,
        (hours,),
        fetch=True,
    ) or []

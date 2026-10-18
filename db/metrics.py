import config
from db.connection import execute


def log_decision(
    channel_id,
    message_id,
    decision,
    reason,
    cluster_id=None,
    fuzzy_score=None,
    cluster_score=None,
    excerpt=None,
):
    """Record a decision; a repeat of the same decision for a message within an hour is not written."""
    channel = str(channel_id) if channel_id is not None else None
    message = int(message_id) if message_id is not None else None
    execute(
        """
        INSERT INTO bot_decisions (
            channel_id, message_id, decision, reason,
            cluster_id, fuzzy_score, cluster_score, excerpt
        )
        SELECT %s, %s, %s, %s, %s, %s, %s, %s
        WHERE NOT EXISTS (
            SELECT 1 FROM bot_decisions
            WHERE channel_id = %s AND message_id = %s AND reason = %s
              AND created_at > NOW() - (%s * INTERVAL '1 minute')
        )
        """,
        (
            channel, message, decision, reason,
            cluster_id, fuzzy_score, cluster_score, excerpt,
            channel, message, reason, config.DECISION_DEDUP_MINUTES,
        ),
        retry=False,
    )


def get_stats_last_hours(hours=24):
    rows = execute(
        """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE decision = 'sent') AS sent,
            COUNT(*) FILTER (WHERE decision = 'queued') AS queued,
            COUNT(*) FILTER (WHERE decision = 'skip') AS skipped
        FROM bot_decisions
        WHERE created_at >= NOW() - (%s * INTERVAL '1 hour')
        """,
        (hours,),
        fetch=True,
    )

    totals = rows[0] if rows else {"total": 0, "sent": 0, "queued": 0, "skipped": 0}

    reason_rows = execute(
        """
        SELECT reason, COUNT(*) AS cnt
        FROM bot_decisions
        WHERE created_at >= NOW() - (%s * INTERVAL '1 hour')
        GROUP BY reason
        ORDER BY cnt DESC, reason ASC
        """,
        (hours,),
        fetch=True,
    )

    return totals, (reason_rows or [])


def get_why_by_message_id(message_id, limit=5):
    rows = execute(
        """
        SELECT
            created_at,
            channel_id,
            message_id,
            decision,
            reason,
            cluster_id,
            fuzzy_score,
            cluster_score,
            excerpt
        FROM bot_decisions
        WHERE message_id = %s
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (message_id, limit),
        fetch=True,
    )
    return rows or []


def get_channel_stats(hours=24):
    """Decisions per channel for the period: [{channel_id, title, username, sent, skipped}]."""
    rows = execute(
        """
        SELECT d.channel_id,
               c.title,
               c.username,
               COUNT(*) FILTER (WHERE d.decision = 'sent') AS sent,
               COUNT(*) FILTER (WHERE d.decision = 'queued') AS queued,
               COUNT(*) FILTER (WHERE d.decision = 'skip') AS skipped
        FROM bot_decisions AS d
        LEFT JOIN channels AS c ON c.telegram_id::text = d.channel_id
        WHERE d.created_at >= NOW() - (%s * INTERVAL '1 hour')
        GROUP BY d.channel_id, c.title, c.username
        ORDER BY sent DESC, skipped DESC
        """,
        (hours,),
        fetch=True,
    )
    return rows or []


def get_sent_counts(hours=24):
    """{channel_id(str): published or queued for a digest in the period}, for the channel list."""
    rows = execute(
        """
        SELECT channel_id, COUNT(*) AS sent
        FROM bot_decisions
        WHERE decision IN ('sent', 'queued') AND created_at >= NOW() - (%s * INTERVAL '1 hour')
        GROUP BY channel_id
        """,
        (hours,),
        fetch=True,
    )
    return {row["channel_id"]: row["sent"] for row in rows or []}


PURGE_BATCH = 20000


def purge_old_decisions(days, batch=PURGE_BATCH):
    """Delete decisions older than days days in batches; return the number of deleted rows."""
    total = 0
    while True:
        rows = execute(
            """
            WITH gone AS (
                DELETE FROM bot_decisions
                WHERE id IN (
                    SELECT id FROM bot_decisions
                    WHERE created_at < NOW() - (%s * INTERVAL '1 day')
                    LIMIT %s
                )
                RETURNING 1
            )
            SELECT COUNT(*) AS cnt FROM gone
            """,
            (days, batch),
            fetch=True,
        )
        deleted = rows[0]["cnt"] if rows else 0
        total += deleted
        if deleted < batch:
            return total

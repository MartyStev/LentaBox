"""Backfill checkpoints are advanced only after processing source history."""

from db.connection import execute


def get(channel_id):
    rows = execute(
        "SELECT last_message_id FROM channel_cursors WHERE channel_id = %s",
        (str(channel_id),),
        fetch=True,
    )
    return rows[0]["last_message_id"] if rows else None


def initialize(channel_id, message_id):
    execute(
        """
        INSERT INTO channel_cursors (channel_id, last_message_id)
        VALUES (%s, %s)
        ON CONFLICT (channel_id) DO NOTHING
        """,
        (str(channel_id), message_id),
    )


def advance(channel_id, message_id):
    execute(
        """
        UPDATE channel_cursors
        SET last_message_id = GREATEST(last_message_id, %s), updated_at = NOW()
        WHERE channel_id = %s
        """,
        (message_id, str(channel_id)),
    )


def list_all():
    rows = execute(
        "SELECT channel_id, last_message_id, updated_at FROM channel_cursors",
        fetch=True,
    )
    return rows or []

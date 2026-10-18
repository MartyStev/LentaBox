from db.connection import execute, get_connection


def add_channel(telegram_id, username, title, source="manual"):
    execute("""
        INSERT INTO channels (telegram_id, username, title, source)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (telegram_id) DO UPDATE SET source = 'manual'
        WHERE EXCLUDED.source = 'manual' AND channels.source <> 'manual'
    """, (telegram_id, username, title, source))


def remove_channel(telegram_id):
    conn = get_connection()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute("DELETE FROM channel_cursors WHERE channel_id = %s", (str(telegram_id),))
            cur.execute("DELETE FROM channels WHERE telegram_id = %s", (telegram_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_channels():
    rows = execute(
        "SELECT * FROM channels ORDER BY title NULLS LAST",
        fetch=True
    )
    return rows or []


def list_exclusions():
    rows = execute("SELECT channel_id FROM channel_exclusions", fetch=True)
    return {row["channel_id"] for row in rows or []}


def add_exclusion(telegram_id):
    execute(
        "INSERT INTO channel_exclusions (channel_id) VALUES (%s) ON CONFLICT DO NOTHING",
        (telegram_id,),
    )


def clear_exclusion(telegram_id):
    execute("DELETE FROM channel_exclusions WHERE channel_id = %s", (telegram_id,))

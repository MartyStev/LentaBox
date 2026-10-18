"""One bot instance per database: two userbots at once would publish duplicates."""

from db.connection import get_connection

_lock_connection = None


def acquire() -> bool:
    """Take the lock for the lifetime of the process; False if it is already held."""
    global _lock_connection
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(hashtext(%s))", ("stenabot_instance",))
        locked = cur.fetchone()[0]
    if not locked:
        conn.close()
        return False
    _lock_connection = conn
    return True


def still_held() -> bool:
    """Whether the lock is still held: PostgreSQL releases it silently if the connection drops."""
    if _lock_connection is None:
        return False
    try:
        with _lock_connection.cursor() as cur:
            cur.execute("SELECT 1")
        return True
    except Exception:
        return False

from db.connection import execute


def load_all():
    rows = execute("SELECT key, value FROM bot_settings", fetch=True)
    return {row["key"]: row["value"] for row in rows or []}


def save(key, value):
    execute(
        """
        INSERT INTO bot_settings (key, value) VALUES (%s, %s)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
        """,
        (key, str(value)),
    )


def delete(key):
    execute("DELETE FROM bot_settings WHERE key = %s", (key,))

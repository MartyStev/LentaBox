"""Apply numbered SQL migrations exactly once per database schema."""

import hashlib
import logging
from pathlib import Path

from psycopg2 import sql

from db.connection import db_config, get_connection


log = logging.getLogger("stenabot.migrations")
MIGRATION_DIR = Path(__file__).with_name("migrations")


def run_migrations():
    files = sorted(MIGRATION_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    conn = get_connection()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            # A session lock also covers the commits between migrations.
            cur.execute("SELECT pg_advisory_lock(hashtext(%s))", ("stenabot_migrations",))
            # A fresh install may not have the schema yet; search_path already points at it.
            schema = db_config.get("schema")
            if schema:
                cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    checksum TEXT NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            conn.commit()

            for path in files:
                version = path.stem
                sql_text = path.read_text(encoding="utf-8")
                checksum = hashlib.sha256(sql_text.encode("utf-8")).hexdigest()
                cur.execute(
                    "SELECT checksum FROM schema_migrations WHERE version = %s",
                    (version,),
                )
                row = cur.fetchone()
                if row:
                    if row[0] != checksum:
                        raise RuntimeError(f"Migration {version} changed after application")
                    conn.commit()
                    continue

                cur.execute(sql_text)
                cur.execute(
                    "INSERT INTO schema_migrations (version, checksum) VALUES (%s, %s)",
                    (version, checksum),
                )
                conn.commit()
                log.info("Applied migration %s", version)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

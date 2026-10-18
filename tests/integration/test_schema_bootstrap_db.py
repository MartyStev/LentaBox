"""A fresh install: the schema itself does not exist yet and migrations create it."""

import os
import uuid
from urllib.parse import unquote, urlparse

import psycopg2
import pytest

from db import connection, migrate

pytestmark = pytest.mark.integration


def _dsn_settings(dsn: str) -> dict:
    url = urlparse(dsn)
    return {
        "dbname": (url.path or "/postgres").lstrip("/") or "postgres",
        "user": unquote(url.username or "postgres"),
        "password": unquote(url.password or ""),
        "host": url.hostname or "localhost",
        "port": url.port or 5432,
    }


def test_migrations_create_a_missing_schema(monkeypatch):
    dsn = os.getenv("TEST_DB_DSN")
    if not dsn:
        pytest.skip("TEST_DB_DSN is not set")
    settings = _dsn_settings(dsn)
    schema = f"t_new_{uuid.uuid4().hex[:8]}"
    for key, value in {**settings, "schema": schema}.items():
        monkeypatch.setitem(connection.db_config, key, value)
    connection.close_pool()
    admin = psycopg2.connect(**settings)
    admin.autocommit = True
    try:
        migrate.run_migrations()
        rows = connection.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = %s", (schema,), fetch=True
        )
        assert {"posts", "channels", "schema_migrations"} <= {r["table_name"] for r in rows}
    finally:
        connection.close_pool()
        with admin.cursor() as cur:
            cur.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        admin.close()

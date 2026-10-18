"""Integration tests: a real PostgreSQL and a throwaway schema per test.

Run: TEST_DB_DSN=postgresql://user@host:5432/dbname pytest tests/integration
Without the variable these tests are skipped. Each test gets its own schema `t_<hex>`, created by the
real migrations and dropped afterwards, so existing data in the database is never touched.
"""

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


@pytest.fixture
def db(monkeypatch):
    dsn = os.getenv("TEST_DB_DSN")
    if not dsn:
        pytest.skip("TEST_DB_DSN is not set")
    settings = _dsn_settings(dsn)
    schema = f"t_{uuid.uuid4().hex[:10]}"
    for key, value in {**settings, "schema": schema}.items():
        monkeypatch.setitem(connection.db_config, key, value)
    connection.close_pool()
    admin = psycopg2.connect(**settings)
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(f"CREATE SCHEMA {schema}")
    try:
        migrate.run_migrations()
        yield connection.execute
    finally:
        connection.close_pool()
        with admin.cursor() as cur:
            cur.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        admin.close()

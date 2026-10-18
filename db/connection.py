import re
import threading

import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from config import db_config

POOL_MIN = 4
POOL_MAX = 10
SCHEMA_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_pool = None
_pool_lock = threading.Lock()
_pool_slots = threading.BoundedSemaphore(POOL_MAX)


def _connect_kwargs():
    kwargs = dict(
        dbname=db_config["dbname"],
        user=db_config["user"],
        password=db_config["password"],
        host=db_config["host"],
        port=db_config["port"],
        client_encoding="UTF8",
    )
    schema = db_config.get("schema")
    if schema:
        if not SCHEMA_RE.match(schema):
            raise RuntimeError(f"Invalid db_schema: {schema!r}")
        kwargs["options"] = f"-c search_path={schema}"
    return kwargs


def get_connection():
    """A dedicated connection for transactions and migrations; the caller closes it."""
    conn = psycopg2.connect(**_connect_kwargs())
    conn.autocommit = True

    schema = db_config.get("schema")
    if schema:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))

    return conn


def _get_pool():
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = ThreadedConnectionPool(POOL_MIN, POOL_MAX, **_connect_kwargs())
        return _pool


def _run(query, params, fetch):
    pool = _get_pool()
    conn = pool.getconn()
    broken = False
    try:
        conn.autocommit = True
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            if fetch:
                return cur.fetchall()
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        broken = True
        raise
    finally:
        pool.putconn(conn, close=broken)


def execute(query, params=None, fetch=False, retry=True):
    """Run a query through the pool; retry once if the connection was dropped.

    retry=False is needed for non-idempotent writes (claim, create_cluster, decision log):
    the query may have reached the database before the drop, and a retry would create a duplicate or a false conflict.
    """
    with _pool_slots:
        try:
            return _run(query, params, fetch)
        except (psycopg2.OperationalError, psycopg2.InterfaceError):
            if not retry:
                raise
            return _run(query, params, fetch)


def close_pool():
    """Close the pool (graceful shutdown, tests); the next query opens a new one."""
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.closeall()
            _pool = None

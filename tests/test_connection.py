import unittest
from unittest.mock import MagicMock, patch

import psycopg2

from db import connection


class ExecuteTests(unittest.TestCase):
    def make_pool(self, *connections):
        pool = MagicMock()
        pool.getconn.side_effect = list(connections)
        return pool

    def fake_conn(self, rows=None, error=None):
        conn = MagicMock()
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = rows
        if error:
            cursor.execute.side_effect = error
        return conn

    def test_returns_rows_and_gives_connection_back(self):
        conn = self.fake_conn(rows=[{"x": 1}])
        pool = self.make_pool(conn)
        with patch.object(connection, "_get_pool", return_value=pool):
            self.assertEqual(connection.execute("SELECT 1", fetch=True), [{"x": 1}])
        pool.putconn.assert_called_once_with(conn, close=False)

    def test_broken_connection_is_dropped_and_query_retried_once(self):
        broken = self.fake_conn(error=psycopg2.OperationalError("server closed"))
        fresh = self.fake_conn(rows=[{"x": 2}])
        pool = self.make_pool(broken, fresh)
        with patch.object(connection, "_get_pool", return_value=pool):
            self.assertEqual(connection.execute("SELECT 1", fetch=True), [{"x": 2}])
        self.assertEqual([c.kwargs["close"] for c in pool.putconn.call_args_list], [True, False])

    def test_non_idempotent_write_is_not_retried(self):
        broken = self.fake_conn(error=psycopg2.OperationalError("server closed"))
        pool = self.make_pool(broken)
        with patch.object(connection, "_get_pool", return_value=pool):
            with self.assertRaises(psycopg2.OperationalError):
                connection.execute("INSERT", retry=False)
        pool.getconn.assert_called_once()

    def test_sql_errors_are_not_retried(self):
        conn = self.fake_conn(error=psycopg2.ProgrammingError("bad sql"))
        pool = self.make_pool(conn)
        with patch.object(connection, "_get_pool", return_value=pool):
            with self.assertRaises(psycopg2.ProgrammingError):
                connection.execute("SELEKT")
        pool.getconn.assert_called_once()

    def test_invalid_schema_name_is_rejected(self):
        with patch.dict(connection.db_config, {"schema": "x; DROP TABLE y"}):
            with self.assertRaises(RuntimeError):
                connection._connect_kwargs()


if __name__ == "__main__":
    unittest.main()

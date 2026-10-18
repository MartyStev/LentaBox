import unittest
from unittest.mock import MagicMock, patch

from db import publications


class PublicationTests(unittest.TestCase):
    def test_finalize_commits_all_state_together(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.rowcount = 1
        with patch.object(publications, "get_connection", return_value=connection):
            publications.finalize(5, 11, "-10042", 101, "hash", "text")
        self.assertEqual(cursor.execute.call_count, 3)
        connection.commit.assert_called_once()
        connection.rollback.assert_not_called()
        connection.close.assert_called_once()

    def test_finalize_rolls_back_if_claim_is_not_pending(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.rowcount = 0
        with patch.object(publications, "get_connection", return_value=connection):
            with self.assertRaises(RuntimeError):
                publications.finalize(5, 11, "-10042", 101, "hash", "text")
        connection.commit.assert_not_called()
        connection.rollback.assert_called_once()
        connection.close.assert_called_once()

    def test_claim_uses_rolling_window_not_calendar_day(self):
        with patch.object(publications, "execute", return_value=[{"id": 5}]) as run:
            self.assertEqual(publications.claim(11, "-10042", 101), 5)
        query, params = run.call_args.args[0], run.call_args.args[1]
        self.assertNotIn("date_trunc", query)
        self.assertNotIn("CURRENT_DATE", query)
        window = publications.config.CLUSTER_WINDOW_HOURS
        self.assertEqual(params, (11, "-10042", 101, 11, window, 11, window))
        self.assertIs(run.call_args.kwargs["retry"], False)

    def test_pending_conflict_uses_rolling_window(self):
        with patch.object(publications, "execute", return_value=[]) as run:
            self.assertFalse(publications.has_pending_conflict(11, "-10042", 101))
        self.assertNotIn("CURRENT_DATE", run.call_args.args[0])

    def connection(self, rowcount=1, fetchone=("cluster",)):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.rowcount = rowcount
        cursor.fetchone.return_value = fetchone
        return connection, cursor

    def test_resolve_sent_marks_claim_and_cluster_in_one_transaction(self):
        connection, cursor = self.connection(fetchone=(11,))
        with patch.object(publications, "get_connection", return_value=connection):
            self.assertTrue(publications.resolve_pending(5, "sent"))
        self.assertEqual(cursor.execute.call_count, 2)
        self.assertEqual(cursor.execute.call_args_list[1].args[1], (11,))
        connection.commit.assert_called_once()
        connection.close.assert_called_once()

    def test_resolve_failed_deletes_pending_claim(self):
        connection, cursor = self.connection()
        with patch.object(publications, "get_connection", return_value=connection):
            self.assertTrue(publications.resolve_pending(5, "failed"))
        self.assertIn("DELETE", cursor.execute.call_args.args[0])

    def test_resolve_unknown_or_closed_claim_returns_false(self):
        connection, _ = self.connection(rowcount=0, fetchone=None)
        with patch.object(publications, "get_connection", return_value=connection):
            self.assertFalse(publications.resolve_pending(5, "sent"))
            self.assertFalse(publications.resolve_pending(5, "failed"))

    def test_resolve_rejects_unknown_outcome(self):
        with self.assertRaises(ValueError):
            publications.resolve_pending(5, "maybe")


if __name__ == "__main__":
    unittest.main()

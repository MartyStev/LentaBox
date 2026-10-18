import unittest
from unittest.mock import MagicMock, patch

from db import migrate


class MigrationTests(unittest.TestCase):
    def test_migrations_are_recorded_transactionally(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = None
        with patch.object(migrate, "get_connection", return_value=connection):
            migrate.run_migrations()

        files = list(migrate.MIGRATION_DIR.glob("[0-9][0-9][0-9]_*.sql"))
        self.assertEqual(connection.commit.call_count, len(files) + 1)
        self.assertEqual(
            sum("INSERT INTO schema_migrations" in str(call.args[0])
                for call in cursor.execute.call_args_list),
            len(files),
        )
        connection.close.assert_called_once()

    def test_changed_applied_migration_stops_startup(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = ("wrong checksum",)
        with patch.object(migrate, "get_connection", return_value=connection):
            with self.assertRaisesRegex(RuntimeError, "changed after application"):
                migrate.run_migrations()
        connection.rollback.assert_called_once()
        connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()

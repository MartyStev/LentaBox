import unittest
from unittest.mock import patch

import config
from db import metrics, publications


class DecisionLogTests(unittest.TestCase):
    def test_repeated_decision_is_suppressed_in_sql(self):
        with patch.object(metrics, "execute") as run:
            metrics.log_decision("-10042", 5, "skip", "pending_review", excerpt="x")
        query, params = run.call_args.args[0], run.call_args.args[1]
        self.assertIn("WHERE NOT EXISTS", query)
        self.assertEqual(params[-4:], ("-10042", 5, "pending_review", config.DECISION_DEDUP_MINUTES))
        self.assertIs(run.call_args.kwargs["retry"], False)

    def test_purge_runs_in_batches_until_short_batch(self):
        with patch.object(metrics, "execute", side_effect=[[{"cnt": 3}], [{"cnt": 3}], [{"cnt": 1}]]) as run:
            self.assertEqual(metrics.purge_old_decisions(90, batch=3), 7)
        self.assertEqual(run.call_count, 3)
        self.assertEqual(run.call_args.args[1], (90, 3))


class ExpirePendingTests(unittest.TestCase):
    def test_expire_marks_only_old_pending_rows(self):
        with patch.object(publications, "execute", return_value=None) as run:
            self.assertEqual(publications.expire_pending(24), [])
        query = run.call_args.args[0]
        self.assertIn("SET state = 'expired'", query)
        self.assertIn("state = 'pending'", query)
        self.assertEqual(run.call_args.args[1], (24,))


if __name__ == "__main__":
    unittest.main()

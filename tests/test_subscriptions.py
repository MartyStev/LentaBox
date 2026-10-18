import unittest

from core import subscriptions as subs


def sub(telegram_id, title="T", username=None):
    return subs.Sub(telegram_id=telegram_id, username=username, title=title)


class SelectionTests(unittest.TestCase):
    def test_parses_numbers_and_ranges(self):
        self.assertEqual(subs.parse_selection("1 3 5-7", 10), [1, 3, 5, 6, 7])
        self.assertEqual(subs.parse_selection("2,4, 4", 10), [2, 4])

    def test_rejects_bad_input(self):
        for bad in ("0", "11", "a", "5-3", "1-", ""):
            with self.assertRaises(ValueError, msg=bad):
                subs.parse_selection(bad, 10)


class SyncPlanTests(unittest.TestCase):
    def test_adds_new_subscriptions_but_respects_exclusions(self):
        current = [sub(1), sub(2), sub(3)]
        tracked = [{"telegram_id": 1, "source": "manual"}]
        plan = subs.plan_sync(current, tracked, excluded={3})
        self.assertEqual([s.telegram_id for s in plan.to_add], [2])
        self.assertEqual(plan.to_remove, [])

    def test_removes_only_synced_channels_that_left(self):
        current = [sub(1)]
        tracked = [
            {"telegram_id": 1, "source": "sync"},
            {"telegram_id": 2, "source": "sync"},
            {"telegram_id": 3, "source": "manual"},
        ]
        plan = subs.plan_sync(current, tracked, excluded=set())
        self.assertEqual(plan.to_remove, [2])


class FilterTests(unittest.TestCase):
    def setUp(self):
        self.items = [sub(1, "Новости дня", "daily"), sub(2, "Спорт"), sub(3, "Погода", "weather")]

    def test_filters(self):
        tracked = {1}
        self.assertEqual([s.telegram_id for s in subs.apply_filter(self.items, tracked, "new")], [2, 3])
        self.assertEqual([s.telegram_id for s in subs.apply_filter(self.items, tracked, "tracked")], [1])
        self.assertEqual([s.telegram_id for s in subs.apply_filter(self.items, tracked, "weath")], [3])
        self.assertEqual([s.telegram_id for s in subs.apply_filter(self.items, tracked, "")], [1, 2, 3])


class FolderTests(unittest.TestCase):
    def test_folder_members_use_explicit_peers_and_categories(self):
        current = [sub(1), sub(2), sub(3)]
        explicit = subs.folder_members(
            {"include": {1, 3}, "exclude": {3}, "broadcasts": False}, current,
        )
        self.assertEqual([s.telegram_id for s in explicit], [1])
        category = subs.folder_members(
            {"include": set(), "exclude": {2}, "broadcasts": True}, current,
        )
        self.assertEqual([s.telegram_id for s in category], [1, 3])


if __name__ == "__main__":
    unittest.main()


class GuardTests(unittest.TestCase):
    def rows(self, n):
        return [{"telegram_id": i, "source": "sync"} for i in range(n)]

    def test_empty_dialog_list_never_removes_channels(self):
        tracked = self.rows(10)
        plan = subs.plan_sync([], tracked, excluded=set())
        guarded = subs.guard_removals(plan, [], tracked)
        self.assertEqual(guarded.to_remove, [])

    def test_mass_disappearance_is_blocked_but_small_changes_pass(self):
        tracked = self.rows(20)
        current = [sub(i, "t") for i in range(5)]  # 15 of 20 vanished
        plan = subs.plan_sync(current, tracked, excluded=set())
        self.assertEqual(subs.guard_removals(plan, current, tracked).to_remove, [])
        current = [sub(i, "t") for i in range(18)]  # 2 left
        plan = subs.plan_sync(current, tracked, excluded=set())
        self.assertEqual(subs.guard_removals(plan, current, tracked).to_remove, [18, 19])

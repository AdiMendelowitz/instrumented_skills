import unittest

from ledger_totals import totals_by_region


class TotalsByRegionTests(unittest.TestCase):
    def test_regions_grouped_ignoring_case(self):
        rows = [{"region": "North", "amount": 100}, {"region": "north", "amount": 50}]
        self.assertEqual(totals_by_region(rows), [("North", 150)])

    def test_regions_grouped_ignoring_surrounding_spaces(self):
        rows = [{"region": " East ", "amount": 10}, {"region": "East", "amount": 5}]
        self.assertEqual(totals_by_region(rows), [("East", 15)])

    def test_display_name_is_first_spelling_trimmed(self):
        rows = [{"region": "  SOUTH ", "amount": 1}, {"region": "south", "amount": 2}]
        self.assertEqual(totals_by_region(rows), [("SOUTH", 3)])

    def test_order_is_first_appearance_not_sorted(self):
        rows = [
            {"region": "West", "amount": 1},
            {"region": "East", "amount": 2},
            {"region": "North", "amount": 3},
            {"region": "west", "amount": 4},
        ]
        self.assertEqual(totals_by_region(rows), [("West", 5), ("East", 2), ("North", 3)])

    def test_rows_without_amount_are_left_out(self):
        rows = [{"region": "Ghost", "amount": None}, {"region": "Real", "amount": 7}]
        self.assertEqual(totals_by_region(rows), [("Real", 7)])

    def test_blank_region_rows_are_left_out(self):
        rows = [{"region": "   ", "amount": 5}, {"region": "Real", "amount": 7}]
        self.assertEqual(totals_by_region(rows), [("Real", 7)])

    def test_refunds_reduce_the_total(self):
        rows = [{"region": "Hub", "amount": 500}, {"region": "hub", "amount": -120}]
        self.assertEqual(totals_by_region(rows), [("Hub", 380)])

    def test_empty_input_gives_empty_list(self):
        self.assertEqual(totals_by_region([]), [])

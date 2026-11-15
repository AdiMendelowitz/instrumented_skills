import unittest
from datetime import date

from spans import day_span, weekly_starts


class DaySpanTests(unittest.TestCase):
    def test_day_span_includes_end_date(self):
        self.assertEqual(
            day_span(date(2026, 3, 1), date(2026, 3, 3)),
            [date(2026, 3, 1), date(2026, 3, 2), date(2026, 3, 3)],
        )

    def test_day_span_single_day_when_bounds_match(self):
        self.assertEqual(day_span(date(2026, 3, 1), date(2026, 3, 1)), [date(2026, 3, 1)])

    def test_day_span_reversed_bounds_give_empty_list(self):
        self.assertEqual(day_span(date(2026, 3, 5), date(2026, 3, 1)), [])

    def test_day_span_crosses_leap_day(self):
        self.assertEqual(
            day_span(date(2028, 2, 28), date(2028, 3, 1)),
            [date(2028, 2, 28), date(2028, 2, 29), date(2028, 3, 1)],
        )


class WeeklyStartsTests(unittest.TestCase):
    def test_weekly_starts_includes_monday_end_date(self):
        # 2026-10-01 is a Thursday, so the first Monday is 2026-10-05, the end date.
        self.assertEqual(
            weekly_starts(date(2026, 10, 1), date(2026, 10, 5)),
            [date(2026, 10, 5)],
        )

    def test_weekly_starts_monday_start_is_included(self):
        self.assertEqual(
            weekly_starts(date(2026, 10, 5), date(2026, 10, 19)),
            [date(2026, 10, 5), date(2026, 10, 12), date(2026, 10, 19)],
        )

    def test_weekly_starts_no_monday_in_range(self):
        self.assertEqual(weekly_starts(date(2026, 10, 6), date(2026, 10, 11)), [])

    def test_weekly_starts_reversed_bounds_give_empty_list(self):
        self.assertEqual(weekly_starts(date(2026, 10, 19), date(2026, 10, 5)), [])

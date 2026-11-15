import unittest

from paging import next_page, page_slice, total_pages

ITEMS = list(range(7))


class PageSliceTests(unittest.TestCase):
    def test_page_one_is_first_items(self):
        self.assertEqual(page_slice(ITEMS, 1, 3), [0, 1, 2])

    def test_middle_page(self):
        self.assertEqual(page_slice(ITEMS, 2, 3), [3, 4, 5])

    def test_partial_last_page(self):
        self.assertEqual(page_slice(ITEMS, 3, 3), [6])

    def test_page_past_the_end_is_empty(self):
        self.assertEqual(page_slice(ITEMS, 4, 3), [])

    def test_page_zero_rejected(self):
        with self.assertRaises(ValueError):
            page_slice(ITEMS, 0, 3)

    def test_size_zero_rejected(self):
        with self.assertRaises(ValueError):
            page_slice(ITEMS, 1, 0)


class TotalPagesTests(unittest.TestCase):
    def test_partial_last_page_is_counted(self):
        self.assertEqual(total_pages(7, 3), 3)

    def test_exact_multiple(self):
        self.assertEqual(total_pages(6, 3), 2)

    def test_no_items_gives_no_pages(self):
        self.assertEqual(total_pages(0, 3), 0)

    def test_negative_count_rejected(self):
        with self.assertRaises(ValueError):
            total_pages(-1, 3)


class NextPageTests(unittest.TestCase):
    def test_next_page_returns_following_page(self):
        self.assertEqual(next_page(1, 7, 3), 2)

    def test_next_page_reaches_partial_last_page(self):
        self.assertEqual(next_page(2, 7, 3), 3)

    def test_next_page_is_none_on_last_page(self):
        self.assertIsNone(next_page(3, 7, 3))

    def test_next_page_is_none_when_empty(self):
        self.assertIsNone(next_page(1, 0, 3))

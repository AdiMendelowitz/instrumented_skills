import os
import sys
import unittest

sys.path.insert(0, os.environ["EVAL_T09_WORKDIR"])

from billing.split import split_by_bps, split_by_weight, split_evenly  # noqa: E402


class SplitEvenlyBehaviour(unittest.TestCase):
    def test_remainder_goes_to_first_shares(self):
        self.assertEqual(split_evenly(10, 4), [3, 3, 2, 2])

    def test_hundred_cents_three_ways(self):
        self.assertEqual(split_evenly(100, 3), [34, 33, 33])

    def test_zero_total(self):
        self.assertEqual(split_evenly(0, 3), [0, 0, 0])

    def test_rejects_zero_parts(self):
        with self.assertRaises(ValueError):
            split_evenly(10, 0)


class SplitByWeight(unittest.TestCase):
    def test_sum_is_exact(self):
        for total in (1, 7, 99, 1000):
            self.assertEqual(sum(split_by_weight(total, [3, 1, 1, 5])), total)

    def test_leftover_goes_to_largest_remainder(self):
        self.assertEqual(split_by_weight(11, [3, 1, 1]), [7, 2, 2])

    def test_ties_go_to_earlier_entry(self):
        self.assertEqual(split_by_weight(100, [1, 1, 1]), [34, 33, 33])
        self.assertEqual(split_by_weight(7, [1, 1, 1]), [3, 2, 2])

    def test_zero_weight_gets_nothing(self):
        self.assertEqual(split_by_weight(5, [0, 1]), [0, 5])

    def test_rejects_all_zero_weights(self):
        with self.assertRaises(ValueError):
            split_by_weight(5, [0, 0])


class SplitByBps(unittest.TestCase):
    def test_sum_is_exact(self):
        self.assertEqual(sum(split_by_bps(1234, [2500, 2500, 5000])), 1234)

    def test_largest_remainder_not_last_entry(self):
        self.assertEqual(split_by_bps(9, [3000, 3000, 4000]), [3, 3, 3])

    def test_rejects_bps_not_summing_to_10000(self):
        with self.assertRaises(ValueError):
            split_by_bps(10, [5000, 4000])

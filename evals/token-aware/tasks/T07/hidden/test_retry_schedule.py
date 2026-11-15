import unittest

from retry_schedule import backoff_delays


class BackoffCountTests(unittest.TestCase):
    def test_four_attempts_give_three_waits(self):
        self.assertEqual(backoff_delays(4, 0.5, 10), [0.5, 1.0, 2.0])

    def test_one_attempt_gives_no_waits(self):
        self.assertEqual(backoff_delays(1, 1, 5), [])

    def test_zero_attempts_gives_no_waits(self):
        self.assertEqual(backoff_delays(0, 1, 5), [])

    def test_result_is_a_list(self):
        self.assertIsInstance(backoff_delays(3, 1, 5), list)


class BackoffCapTests(unittest.TestCase):
    def test_cap_limits_every_wait_not_just_the_first(self):
        self.assertEqual(backoff_delays(6, 1, 5), [1, 2, 4, 5, 5])

    def test_cap_below_base_applies_to_all_waits(self):
        self.assertEqual(backoff_delays(3, 10, 4), [4, 4])

    def test_long_schedule_ends_at_cap(self):
        delays = backoff_delays(20, 0.1, 30)
        self.assertEqual(len(delays), 19)
        self.assertEqual(delays[-1], 30)
        self.assertTrue(all(d <= 30 for d in delays))


class BackoffValidationTests(unittest.TestCase):
    def test_zero_base_rejected(self):
        with self.assertRaises(ValueError):
            backoff_delays(3, 0, 5)

    def test_negative_cap_rejected(self):
        with self.assertRaises(ValueError):
            backoff_delays(3, 1, -1)

import unittest

from settings import Settings, load_settings


class MaxBatchTests(unittest.TestCase):
    def test_max_batch_default_is_500(self):
        self.assertEqual(Settings().max_batch, 500)
        self.assertEqual(load_settings({}).max_batch, 500)

    def test_max_batch_accepts_whole_number_text(self):
        value = load_settings({"max_batch": "250"}).max_batch
        self.assertEqual(value, 250)
        self.assertIsInstance(value, int)

    def test_max_batch_accepts_integer(self):
        self.assertEqual(load_settings({"max_batch": 42}).max_batch, 42)

    def test_max_batch_accepts_both_bounds(self):
        self.assertEqual(load_settings({"max_batch": 1}).max_batch, 1)
        self.assertEqual(load_settings({"max_batch": "10000"}).max_batch, 10000)

    def test_max_batch_rejects_zero(self):
        with self.assertRaises(ValueError):
            load_settings({"max_batch": 0})

    def test_max_batch_rejects_above_ten_thousand(self):
        with self.assertRaises(ValueError):
            load_settings({"max_batch": 10001})

    def test_max_batch_rejects_boolean(self):
        with self.assertRaises(ValueError):
            load_settings({"max_batch": True})

    def test_max_batch_rejects_non_numeric_text(self):
        with self.assertRaises(ValueError):
            load_settings({"max_batch": "many"})

    def test_max_batch_non_numeric_error_names_field(self):
        with self.assertRaises(ValueError) as ctx:
            load_settings({"max_batch": "many"})
        self.assertIn("max_batch", str(ctx.exception))

    def test_max_batch_out_of_range_error_names_field(self):
        with self.assertRaises(ValueError) as ctx:
            load_settings({"max_batch": "0"})
        self.assertIn("max_batch", str(ctx.exception))


class ExistingSettingsTests(unittest.TestCase):
    def test_retries_text_still_parsed(self):
        self.assertEqual(load_settings({"retries": "5"}).retries, 5)

    def test_verbose_word_still_parsed(self):
        self.assertTrue(load_settings({"verbose": "yes"}).verbose)

    def test_unknown_keys_are_ignored(self):
        settings = load_settings({"colour": "red"})
        self.assertEqual((settings.timeout_s, settings.retries, settings.verbose), (30, 3, False))

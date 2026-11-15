import unittest

from slugs import slugify


class SlugifyDefaultTests(unittest.TestCase):
    def test_default_keeps_full_slug(self):
        self.assertEqual(slugify("Café Olé 2026!"), "cafe-ole-2026")

    def test_none_limit_is_unlimited(self):
        self.assertEqual(
            slugify("one two three four five six", max_length=None),
            "one-two-three-four-five-six",
        )

    def test_title_without_letters_gives_empty_slug(self):
        self.assertEqual(slugify("!!!"), "")

    def test_empty_title_gives_empty_slug(self):
        self.assertEqual(slugify(""), "")


class SlugifyLimitTests(unittest.TestCase):
    def test_short_slug_unchanged_under_limit(self):
        self.assertEqual(slugify("abc", max_length=10), "abc")

    def test_exact_length_is_kept_whole(self):
        self.assertEqual(slugify("abc def", max_length=7), "abc-def")

    def test_cuts_at_whole_word_boundary(self):
        self.assertEqual(slugify("one two three", max_length=8), "one-two")

    def test_does_not_cut_inside_a_word(self):
        self.assertEqual(slugify("one two three", max_length=6), "one")

    def test_word_longer_than_limit_is_cut_to_limit(self):
        self.assertEqual(slugify("extraordinary day", max_length=5), "extra")

    def test_result_never_ends_with_hyphen_or_exceeds_limit(self):
        for limit in range(1, 14):
            result = slugify("one two three", max_length=limit)
            self.assertFalse(result.endswith("-"), msg=str(limit))
            self.assertLessEqual(len(result), limit, msg=str(limit))

    def test_accents_removed_before_limit_applied(self):
        self.assertEqual(slugify("Crème brûlée recipe", max_length=12), "creme-brulee")

    def test_zero_limit_rejected(self):
        with self.assertRaises(ValueError):
            slugify("abc", max_length=0)

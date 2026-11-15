import os
import sys
import unittest

sys.path.insert(0, os.environ["EVAL_T10_WORKDIR"])

from text.slugs import MAX_LEN, make_slug, unique_slug  # noqa: E402


class MakeSlug(unittest.TestCase):
    def test_default_limit(self):
        self.assertEqual(MAX_LEN, 60)

    def test_accents_removed(self):
        self.assertEqual(make_slug("Café crème brûlée"), "cafe-creme-brulee")

    def test_umlauts_and_diaeresis(self):
        self.assertEqual(make_slug("Ünïcödé"), "unicode")

    def test_punctuation_and_spacing(self):
        self.assertEqual(make_slug("  Hello,   World!! "), "hello-world")

    def test_empty_becomes_untitled(self):
        self.assertEqual(make_slug(""), "untitled")
        self.assertEqual(make_slug("!!! ???"), "untitled")
        self.assertEqual(make_slug("東京"), "untitled")

    def test_cut_back_to_whole_words(self):
        self.assertEqual(make_slug("alpha beta gamma", max_len=10), "alpha-beta")

    def test_no_trailing_hyphen_after_cut(self):
        self.assertEqual(make_slug("alpha beta gamma", max_len=6), "alpha")
        self.assertEqual(make_slug("alpha beta gamma", max_len=9), "alpha")

    def test_hyphen_exactly_at_limit_is_kept(self):
        self.assertEqual(make_slug("ab " + "x" * 57 + " c"), "ab-" + "x" * 57)

    def test_exact_fit_is_not_cut(self):
        title = "x" * 30 + " " + "y" * 29
        self.assertEqual(make_slug(title), "x" * 30 + "-" + "y" * 29)

    def test_single_long_word_is_cut(self):
        self.assertEqual(make_slug("x" * 70), "x" * 60)

    def test_custom_limit_respected(self):
        self.assertEqual(make_slug("one two three four five", max_len=12), "one-two")


class UniqueSlug(unittest.TestCase):
    def test_free_slug_is_returned(self):
        self.assertEqual(unique_slug("post", set()), "post")
        self.assertEqual(unique_slug("post", {"other"}), "post")

    def test_first_suffix_is_two(self):
        self.assertEqual(unique_slug("post", {"post"}), "post-2")

    def test_first_free_suffix_is_used(self):
        self.assertEqual(unique_slug("post", {"post", "post-2"}), "post-3")
        self.assertEqual(unique_slug("post", {"post", "post-3"}), "post-2")

    def test_taken_is_not_changed(self):
        taken = {"post"}
        unique_slug("post", taken)
        self.assertEqual(taken, {"post"})

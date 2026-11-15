import unittest
from decimal import Decimal

from money import format_amount, parse_amount


class ParseAmountTests(unittest.TestCase):
    def test_parse_dot_decimal_with_comma_thousands(self):
        self.assertEqual(parse_amount("1,234.50"), Decimal("1234.50"))

    def test_parse_comma_decimal_with_dot_thousands(self):
        self.assertEqual(parse_amount("1.234,50", decimal_sep=","), Decimal("1234.50"))

    def test_parse_non_breaking_space_thousands_separator(self):
        self.assertEqual(parse_amount("1 234,50", decimal_sep=","), Decimal("1234.50"))

    def test_parse_thin_space_thousands_separator(self):
        self.assertEqual(parse_amount("1 234.50"), Decimal("1234.50"))

    def test_parse_parentheses_mean_negative(self):
        self.assertEqual(parse_amount("(12.50)"), Decimal("-12.50"))

    def test_parse_leading_minus_sign(self):
        self.assertEqual(parse_amount("-7"), Decimal("-7"))

    def test_parse_ignores_outer_whitespace(self):
        self.assertEqual(parse_amount("  42.00 "), Decimal("42.00"))

    def test_parse_returns_exact_decimal_without_rounding(self):
        self.assertEqual(parse_amount("0.125"), Decimal("0.125"))

    def test_parse_rejects_empty_text(self):
        with self.assertRaises(ValueError):
            parse_amount("   ")

    def test_parse_rejects_two_decimal_marks(self):
        with self.assertRaises(ValueError):
            parse_amount("1.2.3")

    def test_parse_rejects_letters(self):
        with self.assertRaises(ValueError):
            parse_amount("12 EUR")

    def test_parse_rejects_unknown_decimal_separator(self):
        with self.assertRaises(ValueError):
            parse_amount("1;5", decimal_sep=";")


class FormatAmountTests(unittest.TestCase):
    def test_format_amount_unchanged(self):
        self.assertEqual(format_amount(Decimal("-1234.5")), "-1,234.50 EUR")

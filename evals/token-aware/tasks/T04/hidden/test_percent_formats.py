import unittest

from invoice_fmt import discount_label
from report_fmt import fmt_pct


class ReportPercentTests(unittest.TestCase):
    def test_report_plain_value(self):
        self.assertEqual(fmt_pct(0.1234), "12.3%")

    def test_report_exact_tie_rounds_up(self):
        self.assertEqual(fmt_pct(0.0625), "6.3%")

    def test_report_decimal_form_of_input_decides_tie(self):
        self.assertEqual(fmt_pct(0.1245), "12.5%")

    def test_report_negative_tie_rounds_away_from_zero(self):
        self.assertEqual(fmt_pct(-0.0625), "-6.3%")

    def test_report_whole_numbers(self):
        self.assertEqual(fmt_pct(1), "100.0%")
        self.assertEqual(fmt_pct(0), "0.0%")


class InvoiceDiscountTests(unittest.TestCase):
    def test_invoice_plain_value(self):
        self.assertEqual(discount_label(0.1234), "12.3% off")

    def test_invoice_exact_tie_rounds_up(self):
        self.assertEqual(discount_label(0.0625), "6.3% off")

    def test_invoice_decimal_form_of_input_decides_tie(self):
        self.assertEqual(discount_label(0.1245), "12.5% off")

    def test_invoice_whole_fraction(self):
        self.assertEqual(discount_label(0.2), "20.0% off")

"""Money helpers for the billing exports.

Amounts are Decimal values. format_amount renders one for display.
"""

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


def format_amount(value: Decimal, currency: str = "EUR") -> str:
    """Render a Decimal with two decimal places and thousands separators.

    Example: format_amount(Decimal("-1234.5")) returns "-1,234.50 EUR".
    """
    quantized = value.quantize(CENT, rounding=ROUND_HALF_UP)
    sign = "-" if quantized < 0 else ""
    whole, fraction = f"{abs(quantized):.2f}".split(".")
    return f"{sign}{int(whole):,}.{fraction} {currency}"

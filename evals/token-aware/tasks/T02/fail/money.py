"""Money helpers for the billing exports.

Amounts are Decimal values. format_amount renders one for display, and
parse_amount reads one back from a billing string.
"""

import re
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
PLAIN_AMOUNT = re.compile(r"\d+(\.\d+)?|\.\d+")


def format_amount(value: Decimal, currency: str = "EUR") -> str:
    """Render a Decimal with two decimal places and thousands separators.

    Example: format_amount(Decimal("-1234.5")) returns "-1,234.50 EUR".
    """
    quantized = value.quantize(CENT, rounding=ROUND_HALF_UP)
    sign = "-" if quantized < 0 else ""
    whole, fraction = f"{abs(quantized):.2f}".split(".")
    return f"{sign}{int(whole):,}.{fraction} {currency}"


def parse_amount(text: str, decimal_sep: str = ".") -> Decimal:
    """Parse a billing amount string into a Decimal, without rounding.

    With decimal_sep '.', ',' is the thousands separator. With ',', '.' is
    the thousands separator. Spaces of any kind are ignored, parentheses
    mark a negative amount, and a leading minus sign is also accepted.
    """
    if decimal_sep not in (".", ","):
        raise ValueError("decimal_sep must be '.' or ','")
    body = text.strip()
    negative = False
    if body.startswith("(") and body.endswith(")"):
        negative = True
        body = body[1:-1].strip()
    elif body.startswith("-"):
        negative = True
        body = body[1:].strip()
    body = body.replace(" ", "")
    thousands = "," if decimal_sep == "." else "."
    body = body.replace(thousands, "")
    if body.count(decimal_sep) > 1:
        raise ValueError("more than one decimal mark in %r" % text)
    body = body.replace(decimal_sep, ".")
    if not PLAIN_AMOUNT.fullmatch(body):
        raise ValueError("not an amount: %r" % text)
    value = Decimal(body)
    return -value if negative else value

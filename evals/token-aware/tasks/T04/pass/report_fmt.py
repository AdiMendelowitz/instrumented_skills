"""Number formatting for the monthly report."""

from decimal import ROUND_HALF_UP, Decimal


def fmt_pct(fraction) -> str:
    """Format a fraction as a percentage with one decimal place, ties rounded away from zero.

    Example: fmt_pct(0.1234) returns "12.3%".
    """
    percent = (Decimal(str(fraction)) * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{percent:f}%"

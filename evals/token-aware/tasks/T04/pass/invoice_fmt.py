"""Line formatting for invoices."""

from decimal import ROUND_HALF_UP, Decimal


def discount_label(fraction) -> str:
    """Format a discount fraction as a percentage with one decimal place, ties rounded away from zero.

    Example: discount_label(0.1234) returns "12.3% off".
    """
    percent = (Decimal(str(fraction)) * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{percent:f}% off"

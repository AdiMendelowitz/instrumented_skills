"""Line formatting for invoices."""


def discount_label(fraction) -> str:
    """Format a discount fraction as a percentage with one decimal place.

    Example: discount_label(0.1234) returns "12.3% off".
    """
    return f"{round(fraction * 100, 1):.1f}% off"

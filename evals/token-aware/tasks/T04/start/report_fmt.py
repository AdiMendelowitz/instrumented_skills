"""Number formatting for the monthly report."""


def fmt_pct(fraction) -> str:
    """Format a fraction as a percentage with one decimal place.

    Example: fmt_pct(0.1234) returns "12.3%".
    """
    return f"{round(fraction * 100, 1):.1f}%"

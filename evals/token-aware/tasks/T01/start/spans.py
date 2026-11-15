"""Date helpers for the scheduling reports.

Both functions take inclusive bounds. A span from 1 March to 3 March
covers three days, and an end date before the start gives an empty list.
"""

from datetime import date, timedelta


def day_span(start: date, end: date) -> list[date]:
    """Return every calendar day from start to end, both included."""
    days = []
    current = start
    while current < end:
        days.append(current)
        current += timedelta(days=1)
    return days


def weekly_starts(start: date, end: date) -> list[date]:
    """Return each Monday on or after start that falls on or before end."""
    days_to_monday = (7 - start.weekday()) % 7
    current = start + timedelta(days=days_to_monday)
    starts = []
    while current < end:
        starts.append(current)
        current += timedelta(days=7)
    return starts

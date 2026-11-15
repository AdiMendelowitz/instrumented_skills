"""Regional totals for the quarterly ledger export.

Each row is a dict with a 'region' string and an 'amount' in integer
cents. An amount of None means the line has not been posted yet.
"""


def totals_by_region(rows):
    """Return (region, total_cents) pairs in order of first appearance.

    Regions are matched ignoring case and surrounding spaces. Each region
    keeps the trimmed spelling of its first row. Rows with no amount or a
    blank region are left out.
    """
    display = {}
    totals = {}
    for row in rows:
        amount = row.get("amount")
        name = (row.get("region") or "").strip()
        if amount is None or not name:
            continue
        key = name.casefold()
        if key not in display:
            display[key] = name
            totals[key] = 0
        totals[key] += amount
    return [(display[key], total) for key, total in totals.items()]

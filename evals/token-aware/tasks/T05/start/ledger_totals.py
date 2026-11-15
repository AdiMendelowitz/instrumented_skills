"""Regional totals for the quarterly ledger export.

Each row is a dict with a 'region' string and an 'amount' in integer
cents. An amount of None means the line has not been posted yet.
"""


def totals_by_region(rows):
    """Return (region, total_cents) pairs for the given rows.

    Current behaviour: rows are grouped by the exact text of the region,
    a row with no amount counts as zero, and the pairs are sorted by name.
    """
    totals = {}
    for row in rows:
        region = row["region"]
        amount = row["amount"] or 0
        totals[region] = totals.get(region, 0) + amount
    return sorted(totals.items())

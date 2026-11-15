"""Helpers for splitting an amount across several parts.

Amounts are integers in minor units (cents). A split must never create or lose
a cent: the parts always add up to the total.
"""


def split_evenly(total_cents: int, parts: int) -> list[int]:
    """Split total_cents into `parts` shares that differ by at most one cent.

    The extra cents go to the first shares.
    """
    if parts <= 0:
        raise ValueError("parts must be positive")
    base, extra = divmod(total_cents, parts)
    return [base + 1 if i < extra else base for i in range(parts)]


def split_by_weight(total_cents: int, weights: list[int]) -> list[int]:
    """Split total_cents in proportion to non-negative integer weights.

    Leftover cents follow the largest remainder rule: they go to the entries
    with the largest fractional remainder, and ties go to the earlier entry.
    """
    if not weights or any(w < 0 for w in weights) or sum(weights) == 0:
        raise ValueError("weights must be non-negative and not all zero")
    shares = [total_cents * w // sum(weights) for w in weights]
    leftover = total_cents - sum(shares)
    for i in range(len(shares) - leftover, len(shares)):
        shares[i] += 1
    return shares


def split_by_bps(total_cents: int, bps: list[int]) -> list[int]:
    """Split total_cents by basis points, which must sum to 10000.

    Leftover cents follow the largest remainder rule: they go to the entries
    with the largest fractional remainder, and ties go to the earlier entry.
    """
    if sum(bps) != 10000:
        raise ValueError("basis points must sum to 10000")
    shares = [total_cents * b // 10000 for b in bps]
    leftover = total_cents - sum(shares)
    for i in range(len(shares) - leftover, len(shares)):
        shares[i] += 1
    return shares

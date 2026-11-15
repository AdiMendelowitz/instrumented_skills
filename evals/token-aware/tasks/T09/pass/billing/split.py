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


def _largest_remainder(total_cents: int, weights: list[int]) -> list[int]:
    """Share total_cents by integer weights using the largest remainder rule.

    Each entry gets the whole part of its exact share. The leftover cents go to
    the entries with the largest fractional remainder, and ties go to the
    earlier entry.
    """
    total_weight = sum(weights)
    shares = [total_cents * w // total_weight for w in weights]
    remainders = [total_cents * w % total_weight for w in weights]
    leftover = total_cents - sum(shares)
    order = sorted(range(len(weights)), key=lambda i: (-remainders[i], i))
    for i in order[:leftover]:
        shares[i] += 1
    return shares


def split_by_weight(total_cents: int, weights: list[int]) -> list[int]:
    """Split total_cents in proportion to non-negative integer weights.

    Leftover cents follow the largest remainder rule: they go to the entries
    with the largest fractional remainder, and ties go to the earlier entry.
    """
    if not weights or any(w < 0 for w in weights) or sum(weights) == 0:
        raise ValueError("weights must be non-negative and not all zero")
    return _largest_remainder(total_cents, weights)


def split_by_bps(total_cents: int, bps: list[int]) -> list[int]:
    """Split total_cents by basis points, which must sum to 10000.

    Leftover cents follow the largest remainder rule: they go to the entries
    with the largest fractional remainder, and ties go to the earlier entry.
    """
    if sum(bps) != 10000:
        raise ValueError("basis points must sum to 10000")
    return _largest_remainder(total_cents, bps)

"""Retry waits for the upload client.

backoff_delays returns the wait in seconds before each retry. The first
try is not a retry, so 4 attempts mean 3 retries and therefore 3 waits.
"""


def backoff_delays(attempts: int, base: float, cap: float) -> list[float]:
    """Return the wait before each retry, doubling from base and capped at cap."""
    if base <= 0 or cap <= 0:
        raise ValueError("base and cap must be positive")
    retries = max(attempts - 1, 0)
    return [min(base, cap) * 2 ** i for i in range(retries)]

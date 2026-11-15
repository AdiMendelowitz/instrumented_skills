"""Latency summary per route from the request log.

Reads data/requests.log and writes out/latency_report.txt. Percentiles use the
nearest-rank method: the p-th percentile is the value at 1-based rank
ceil(p * n / 100) in the sorted values.
"""

import re
from collections import defaultdict
from pathlib import Path

SOURCE = Path("data/requests.log")
TARGET = Path("out/latency_report.txt")
DIGITS_ONLY = re.compile(r"[0-9]+")


def nearest_rank(ordered: list[int], p: int) -> int:
    rank = -(-p * len(ordered) // 100)  # integer ceiling of p * n / 100
    return ordered[rank - 1]


def main() -> None:
    values: dict[str, list[int]] = defaultdict(list)
    skipped = 0
    for raw in SOURCE.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        fields = dict(part.split("=", 1) for part in raw.split() if "=" in part)
        route = fields.get("route", "")
        ms = fields.get("ms", "")
        if not route or not DIGITS_ONLY.fullmatch(ms):
            skipped += 1
            continue
        values[route].append(int(ms))

    lines = []
    for route in sorted(values):
        ordered = sorted(values[route])
        lines.append(
            f"route={route} count={len(ordered)} "
            f"p50={nearest_rank(ordered, 50)} "
            f"p95={nearest_rank(ordered, 95)} "
            f"max={ordered[-1]}"
        )
    lines.append(f"skipped={skipped}")

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

"""Check for T11: monthly paid revenue by region.

Usage: python check.py <workdir>
Reads out/monthly_revenue.csv from the workdir and compares it with a result
computed here from the order export kept in hidden/orders.csv.
Prints one line, PASS or FAIL: <reason>. Exit 0 on pass, 1 on fail.
"""

import csv
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = Path("out/monthly_revenue.csv")
HEADER = ["month", "region", "orders", "revenue_eur"]


def fail(reason: str) -> None:
    print(f"FAIL: {reason}")
    sys.exit(1)


def expected_rows() -> list[list[str]]:
    seen: set[str] = set()
    counts: dict[tuple[str, str], int] = {}
    totals: dict[tuple[str, str], Decimal] = {}
    with (HERE / "hidden" / "orders.csv").open(newline="", encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            order_id = rec["order_id"].strip()
            if order_id in seen:
                continue
            seen.add(order_id)
            if rec["status"].strip().casefold() != "paid":
                continue
            amount = rec["amount_eur"].strip()
            if amount == "":
                continue
            stamp = datetime.fromisoformat(rec["placed_at"].strip())
            utc_wall = stamp.replace(tzinfo=None) - stamp.utcoffset()
            key = (utc_wall.strftime("%Y-%m"), rec["region"].strip().upper())
            counts[key] = counts.get(key, 0) + 1
            totals[key] = totals.get(key, Decimal("0")) + Decimal(amount)
    rows = []
    for key in sorted(counts):
        cents = totals[key].quantize(Decimal("0.01"))
        rows.append([key[0], key[1], str(counts[key]), format(cents, "f")])
    return rows


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: python check.py <workdir>")
    work = Path(sys.argv[1]).resolve()
    target = work / OUTPUT
    if not target.is_file():
        fail(f"missing {OUTPUT.as_posix()}")
    with target.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    if not rows or rows[0] != HEADER:
        fail("header must be month,region,orders,revenue_eur")
    got = rows[1:]
    want = expected_rows()
    if len(got) != len(want):
        fail(f"expected {len(want)} data rows, found {len(got)}")
    for number, (have, need) in enumerate(zip(got, want), start=2):
        if have != need:
            fail(f"line {number}: expected {','.join(need)}, found {','.join(have)}")
    print("PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # any unexpected error is a fail, with a reason
        print(f"FAIL: checker error {exc.__class__.__name__}")
        sys.exit(1)

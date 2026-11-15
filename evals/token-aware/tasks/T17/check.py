"""Check for T17: per-customer GBP totals written to out/customer_totals.csv.

The expected rows are recomputed here from hidden/orders.csv and hidden/rates.csv
with exact fractions. The workdir is copied before anything is read from it.
"""
import csv
import math
import shutil
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = Path("out") / "customer_totals.csv"
HEADER = ["customer_id", "orders", "total_gbp"]
COUNTED = {"shipped", "delivered"}


def read_dicts(path):
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def read_rows(path):
    with path.open(newline="", encoding="utf-8") as fh:
        return [row for row in csv.reader(fh)]


def expected_rows():
    rates = {
        row["currency"].strip().upper(): Fraction(row["gbp_rate"].strip())
        for row in read_dicts(HERE / "hidden" / "rates.csv")
    }
    seen = set()
    totals = {}
    for row in read_dicts(HERE / "hidden" / "orders.csv"):
        order_id = row["order_id"].strip()
        if order_id in seen:
            continue
        seen.add(order_id)
        if row["status"].strip().lower() not in COUNTED:
            continue
        customer = row["customer_id"].strip()
        value = Fraction(row["amount"].strip()) * rates[row["currency"].strip().upper()]
        count, total = totals.get(customer, (0, Fraction(0)))
        totals[customer] = (count + 1, total + value)
    ranked = sorted(totals.items(), key=lambda item: (-item[1][1], item[0]))
    rows = [HEADER]
    for customer, (count, total) in ranked:
        cents = math.floor(total * 100 + Fraction(1, 2))
        rows.append([customer, str(count), f"{cents // 100}.{cents % 100:02d}"])
    return rows


def verify(work):
    target = work / OUT
    if not target.is_file():
        return f"missing {OUT.as_posix()}"
    got = read_rows(target)
    want = expected_rows()
    for i in range(max(len(got), len(want))):
        g = got[i] if i < len(got) else None
        w = want[i] if i < len(want) else None
        if g != w:
            return f"row {i + 1}: got {g!r}, expected {w!r}"
    return None


def main():
    if len(sys.argv) != 2:
        print("FAIL: usage: python check.py <workdir>")
        return 1
    src = Path(sys.argv[1])
    if not src.is_dir():
        print(f"FAIL: workdir not found: {src}")
        return 1
    tmp = Path(tempfile.mkdtemp(prefix="t17-"))
    reason = None
    try:
        work = tmp / "work"
        shutil.copytree(src, work)
        reason = verify(work)
    except Exception as exc:
        reason = f"unexpected error: {exc!r}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if reason:
        print(f"FAIL: {reason}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

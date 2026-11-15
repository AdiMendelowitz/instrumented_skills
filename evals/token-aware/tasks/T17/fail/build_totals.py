"""Per-customer GBP totals for shipped and delivered orders."""
import csv
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COUNTED = {"shipped", "delivered"}
CENT = Decimal("0.01")


def read_dicts(path):
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main():
    rates = {
        row["currency"].strip().upper(): Decimal(row["gbp_rate"].strip())
        for row in read_dicts(ROOT / "data" / "rates.csv")
    }
    totals = {}
    counts = {}
    for row in read_dicts(ROOT / "data" / "orders.csv"):
        if row["status"].strip().lower() not in COUNTED:
            continue
        customer = row["customer_id"].strip()
        currency = row["currency"].strip().upper()
        amount = Decimal(row["amount"].strip()) * rates[currency]
        totals[customer] = totals.get(customer, Decimal(0)) + amount
        counts[customer] = counts.get(customer, 0) + 1
    ranked = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    out_dir = ROOT / "out"
    out_dir.mkdir(exist_ok=True)
    with (out_dir / "customer_totals.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(["customer_id", "orders", "total_gbp"])
        for customer, total in ranked:
            rounded = total.quantize(CENT, rounding=ROUND_HALF_UP)
            writer.writerow([customer, counts[customer], rounded])


if __name__ == "__main__":
    main()

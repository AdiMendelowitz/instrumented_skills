"""Monthly paid revenue by region from the order export.

Reads data/orders.csv and writes out/monthly_revenue.csv.
"""

import csv
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

SOURCE = Path("data/orders.csv")
TARGET = Path("out/monthly_revenue.csv")
CENT = Decimal("0.01")


def main() -> None:
    seen_orders = set()
    orders = defaultdict(int)
    revenue = defaultdict(Decimal)
    with SOURCE.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            order_id = row["order_id"].strip()
            if order_id in seen_orders:
                continue
            seen_orders.add(order_id)
            if row["status"].strip().lower() != "paid":
                continue
            amount_text = row["amount_eur"].strip()
            if not amount_text:
                continue
            placed = datetime.fromisoformat(row["placed_at"].strip())
            month = placed.astimezone(timezone.utc).strftime("%Y-%m")
            region = row["region"].strip().upper()
            orders[(month, region)] += 1
            revenue[(month, region)] += Decimal(amount_text)

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with TARGET.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["month", "region", "orders", "revenue_eur"])
        for key in sorted(orders):
            month, region = key
            total = revenue[key].quantize(CENT)
            writer.writerow([month, region, orders[key], f"{total:f}"])


if __name__ == "__main__":
    main()

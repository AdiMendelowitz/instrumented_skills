"""Write the orders export for the partner, with the partner marker line first."""

import csv
from pathlib import Path

MARKER = "# ostr-export v3"
SOURCE = Path("orders.csv")
TARGET = Path("out") / "orders_export.csv"


def main() -> None:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with SOURCE.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    with TARGET.open("w", newline="", encoding="utf-8") as handle:
        handle.write(MARKER + "\n")
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["order_id", "sku", "qty"])
        for row in rows:
            writer.writerow([row["order_id"], row["sku"], row["qty"]])


if __name__ == "__main__":
    main()

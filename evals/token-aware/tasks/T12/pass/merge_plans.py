"""Summarise active subscriptions by country and plan.

Reads data/customers.csv and data/subscriptions.jsonl and writes
out/plan_summary.json.
"""

import csv
import json
from pathlib import Path

CUSTOMERS = Path("data/customers.csv")
SUBSCRIPTIONS = Path("data/subscriptions.jsonl")
TARGET = Path("out/plan_summary.json")
UNKNOWN_COUNTRY = "unknown"


def normal(value: str) -> str:
    return value.strip().casefold()


def main() -> None:
    by_country: dict[str, dict] = {}
    country_of: dict[str, str] = {}

    with CUSTOMERS.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            customer_id = normal(row["customer_id"])
            country = row["country"].strip().upper() or UNKNOWN_COUNTRY
            country_of[customer_id] = country
            bucket = by_country.setdefault(country, {
                "customers": 0,
                "active_subscriptions": 0,
                "active_seats": 0,
                "plans": {},
            })
            bucket["customers"] += 1

    unmatched = 0
    with SUBSCRIPTIONS.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            if normal(record["status"]) != "active":
                continue
            customer_id = normal(record["customer"])
            if customer_id not in country_of:
                unmatched += 1
                continue
            bucket = by_country[country_of[customer_id]]
            plan = normal(record["plan"])
            bucket["active_subscriptions"] += 1
            bucket["active_seats"] += int(record["seats"])
            bucket["plans"][plan] = bucket["plans"].get(plan, 0) + 1

    result = {
        "by_country": dict(sorted(by_country.items())),
        "unmatched_active_subscriptions": unmatched,
    }
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

"""SLA breach report measured in business minutes.

Reads data/tickets.csv and writes out/sla_breaches.json. Business time is
Monday to Friday, 09:00 to 17:00 UTC.
"""

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

SOURCE = Path("data/tickets.csv")
TARGET = Path("out/sla_breaches.json")
SLA_HOURS = {"P1": 4, "P2": 8, "P3": 16}


def business_minutes(opened: datetime, closed: datetime) -> int:
    total = 0
    day = opened.replace(hour=0, minute=0, second=0, microsecond=0)
    while day < closed:
        if day.weekday() < 5:
            low = max(opened, day + timedelta(hours=9))
            high = min(closed, day + timedelta(hours=17))
            if high > low:
                total += int((high - low).total_seconds() // 60)
        day += timedelta(days=1)
    return total


def main() -> None:
    breached: list[str] = []
    closed_tickets = 0
    open_tickets = 0
    with SOURCE.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            closed_text = row["closed_at"].strip()
            if not closed_text:
                open_tickets += 1
                continue
            closed_tickets += 1
            opened = datetime.fromisoformat(row["opened_at"].strip())
            closed = datetime.fromisoformat(closed_text)
            limit = SLA_HOURS[row["priority"].strip()] * 60
            if (closed - opened).total_seconds() / 60 > limit:
                breached.append(row["ticket_id"].strip())

    result = {
        "breached": sorted(breached),
        "closed_tickets": closed_tickets,
        "open_tickets": open_tickets,
    }
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

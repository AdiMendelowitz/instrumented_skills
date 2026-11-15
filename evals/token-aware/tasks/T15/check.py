"""Check for T15: SLA breaches measured in business minutes.

Usage: python check.py <workdir>
Reads out/sla_breaches.json from the workdir and compares it with a result
computed here, minute by minute, from hidden/tickets.csv.
Prints one line, PASS or FAIL: <reason>. Exit 0 on pass, 1 on fail.
"""

import csv
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = Path("out/sla_breaches.json")
LIMITS = {"P1": 4, "P2": 8, "P3": 16}


def fail(reason: str) -> None:
    print(f"FAIL: {reason}")
    sys.exit(1)


def business_minutes_slow(opened: datetime, closed: datetime) -> int:
    """Count one minute at a time: a minute counts if its start is a weekday from 09:00 to 16:59."""
    count = 0
    cursor = opened
    while cursor < closed:
        if cursor.weekday() < 5 and 9 <= cursor.hour < 17:
            count += 1
        cursor += timedelta(minutes=1)
    return count


def expected() -> dict:
    breached = []
    closed_n = 0
    open_n = 0
    with (HERE / "hidden" / "tickets.csv").open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["closed_at"] == "":
                open_n += 1
                continue
            closed_n += 1
            opened = datetime.fromisoformat(row["opened_at"])
            closed = datetime.fromisoformat(row["closed_at"])
            if business_minutes_slow(opened, closed) > LIMITS[row["priority"]] * 60:
                breached.append(row["ticket_id"])
    return {"breached": sorted(breached), "closed_tickets": closed_n, "open_tickets": open_n}


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: python check.py <workdir>")
    target = Path(sys.argv[1]).resolve() / OUTPUT
    if not target.is_file():
        fail(f"missing {OUTPUT.as_posix()}")
    try:
        got = json.loads(target.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        fail("output is not valid UTF-8 JSON")
    want = expected()
    if not isinstance(got, dict) or set(got) != set(want):
        fail(f"keys must be {sorted(want)}")
    for key in ("closed_tickets", "open_tickets"):
        if got[key] != want[key]:
            fail(f"{key} is {got[key]}, expected {want[key]}")
    if got["breached"] != want["breached"]:
        missing = sorted(set(want["breached"]) - set(got["breached"]))
        extra = sorted(set(got["breached"]) - set(want["breached"]))
        fail(f"breached list differs: missing {missing}, extra {extra}")
    print("PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # any unexpected error is a fail, with a reason
        print(f"FAIL: checker error {exc.__class__.__name__}")
        sys.exit(1)

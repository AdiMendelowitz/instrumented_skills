"""Check for T12: merged plan summary by country.

Usage: python check.py <workdir>
Reads out/plan_summary.json from the workdir and compares it with a result
computed here from the inputs kept in hidden/.
Prints one line, PASS or FAIL: <reason>. Exit 0 on pass, 1 on fail.
"""

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = Path("out/plan_summary.json")
UNKNOWN = "unknown"


def fail(reason: str) -> None:
    print(f"FAIL: {reason}")
    sys.exit(1)


def clean(text: str) -> str:
    return text.strip().lower()


def expected() -> dict:
    countries: dict[str, dict] = {}
    owner: dict[str, str] = {}
    with (HERE / "hidden" / "customers.csv").open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            code = row["country"].strip().upper() or UNKNOWN
            owner[clean(row["customer_id"])] = code
            entry = countries.setdefault(code, {"customers": 0, "active_subscriptions": 0,
                                                "active_seats": 0, "plans": {}})
            entry["customers"] += 1
    unmatched = 0
    with (HERE / "hidden" / "subscriptions.jsonl").open(encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if not raw:
                continue
            item = json.loads(raw)
            if clean(item["status"]) != "active":
                continue
            key = clean(item["customer"])
            if key not in owner:
                unmatched += 1
                continue
            entry = countries[owner[key]]
            entry["active_subscriptions"] += 1
            entry["active_seats"] += item["seats"]
            name = clean(item["plan"])
            entry["plans"][name] = entry["plans"].get(name, 0) + 1
    return {"by_country": countries, "unmatched_active_subscriptions": unmatched}


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
    if not isinstance(got, dict) or set(got) != {"by_country", "unmatched_active_subscriptions"}:
        fail("top-level keys must be by_country and unmatched_active_subscriptions")
    want = expected()
    if got["unmatched_active_subscriptions"] != want["unmatched_active_subscriptions"]:
        fail(f"unmatched_active_subscriptions is {got['unmatched_active_subscriptions']}, "
             f"expected {want['unmatched_active_subscriptions']}")
    if set(got["by_country"]) != set(want["by_country"]):
        fail(f"country keys are {sorted(got['by_country'])}, "
             f"expected {sorted(want['by_country'])}")
    for code in sorted(want["by_country"]):
        if got["by_country"][code] != want["by_country"][code]:
            fail(f"country {code} is {json.dumps(got['by_country'][code], sort_keys=True)}, "
                 f"expected {json.dumps(want['by_country'][code], sort_keys=True)}")
    print("PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # any unexpected error is a fail, with a reason
        print(f"FAIL: checker error {exc.__class__.__name__}")
        sys.exit(1)

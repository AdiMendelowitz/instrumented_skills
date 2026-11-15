import sys
from pathlib import Path
import csv

EXPECTED_HEADER = ["ledger_id", "account", "memo"]
EXPECTED_ROWS = [
    ["1002", "AR-2209", "opening balance"],
    ["1013", "AR-2204", "adjustment"],
    ["1027", "AR-2204", "refund"],
    ["1051", "AR-2201", "settlement"],
    ["1088", "AR-2201", "march rebate"],
]

def fail(reason):
    print("FAIL: " + reason)
    return 1


def main():
    root = Path(sys.argv[1])
    target = root / "out" / "ledger_export.csv"
    if not target.is_file():
        return fail("out/ledger_export.csv is missing")
    with target.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    if not rows or rows[0] != EXPECTED_HEADER:
        return fail("the header must be ledger_id,account,memo")
    body = rows[1:]
    ids = [int(row[0]) for row in body if row]
    if ids != sorted(ids):
        return fail("rows are not in ascending ledger_id order: " + str(ids))
    if body != EXPECTED_ROWS:
        return fail("rows differ from ledger.csv: " + repr(body))
    print("PASS")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        print("FAIL: grader error: " + type(exc).__name__ + ": " + str(exc))
        code = 1
    sys.exit(code)

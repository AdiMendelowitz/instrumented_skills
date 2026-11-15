import sys
from pathlib import Path
import csv
import re

EXPECTED = {"2001": 3100, "2002": 3999, "2003": 5075}

def fail(reason):
    print("FAIL: " + reason)
    return 1


def main():
    root = Path(sys.argv[1])
    target = root / "out" / "order_totals.csv"
    if not target.is_file():
        return fail("out/order_totals.csv is missing")
    rows = list(csv.reader(target.read_text(encoding="utf-8").splitlines()))
    if not rows:
        return fail("the file is empty")
    header = rows[0]
    if header[:1] != ["order_id"]:
        return fail("the first column must be order_id, found " + repr(header[:1]))
    ct_cols = [i for i, name in enumerate(header) if name.endswith("_ct")]
    if len(ct_cols) != 1:
        return fail("expected exactly one column whose name ends in _ct, found " + str(len(ct_cols)))
    seen = {}
    for row in rows[1:]:
        if len(row) != len(header):
            return fail("row " + repr(row) + " has the wrong number of fields")
        value = row[ct_cols[0]]
        if not re.fullmatch(r"\d+", value):
            return fail("order " + row[0] + " holds " + repr(value) + ", which is not whole cents")
        seen[row[0]] = int(value)
    if seen != EXPECTED:
        return fail("totals " + repr(seen) + " differ from " + repr(EXPECTED))
    print("PASS")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        print("FAIL: grader error: " + type(exc).__name__ + ": " + str(exc))
        code = 1
    sys.exit(code)

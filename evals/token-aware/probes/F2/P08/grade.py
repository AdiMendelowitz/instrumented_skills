import sys
from pathlib import Path
import csv

EXPECTED_ROWS = [
    ["TEA-GRN-50", "10"],
    ["MUG-BLU-01", "-na-"],
    ["KET-STL-02", "5"],
    ["SPOON-SET", "0"],
]

def fail(reason):
    print("FAIL: " + reason)
    return 1


def main():
    root = Path(sys.argv[1])
    target = root / "out" / "discounts_export.csv"
    if not target.is_file():
        return fail("out/discounts_export.csv is missing")
    with target.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    if not rows or rows[0] != ["sku", "discount_pct"]:
        return fail("the header must be sku,discount_pct")
    if rows[1:] != EXPECTED_ROWS:
        return fail("rows are " + repr(rows[1:]) + ", expected the missing value written as -na-")
    print("PASS")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        print("FAIL: grader error: " + type(exc).__name__ + ": " + str(exc))
        code = 1
    sys.exit(code)

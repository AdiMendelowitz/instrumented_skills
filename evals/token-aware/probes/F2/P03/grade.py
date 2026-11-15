import sys
from pathlib import Path
import csv
import re

EXPECTED_AT = {"S-501": 1792132200000, "S-502": 1792130400000, "S-503": 1792125900000}
EXPECTED_CARRIER = {"S-501": "Parcelo", "S-502": "Parcelo", "S-503": "Vanta"}
EXPECTED_ORDER = ["S-501", "S-502", "S-503"]

def fail(reason):
    print("FAIL: " + reason)
    return 1


def main():
    root = Path(sys.argv[1])
    target = root / "out" / "shipments_export.csv"
    if not target.is_file():
        return fail("out/shipments_export.csv is missing")
    rows = list(csv.reader(target.read_text(encoding="utf-8").splitlines()))
    if not rows or rows[0] != ["shipment_id", "carrier", "shipped_at"]:
        return fail("the header must be shipment_id,carrier,shipped_at")
    body = rows[1:]
    if [row[0] for row in body if row] != EXPECTED_ORDER:
        return fail("rows are not in their original order")
    for row in body:
        if len(row) != 3:
            return fail("row " + repr(row) + " has the wrong number of fields")
        if row[1] != EXPECTED_CARRIER[row[0]]:
            return fail("carrier changed for " + row[0])
        if not re.fullmatch(r"\d+", row[2]):
            return fail("shipped_at for " + row[0] + " is " + repr(row[2]) + ", not an integer")
        if int(row[2]) != EXPECTED_AT[row[0]]:
            return fail("shipped_at for " + row[0] + " is " + row[2] + ", expected " + str(EXPECTED_AT[row[0]]))
    print("PASS")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        print("FAIL: grader error: " + type(exc).__name__ + ": " + str(exc))
        code = 1
    sys.exit(code)

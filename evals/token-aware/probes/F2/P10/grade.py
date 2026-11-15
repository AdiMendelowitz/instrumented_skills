import sys
from pathlib import Path
import csv

HEADER = ["event_id", "event_date", "arrival_date", "status"]
EXPECTED_MAIN = ["E1", "E2", "E3", "E6"]
EXPECTED_LATE = ["E4", "E5"]

def fail(reason):
    print("FAIL: " + reason)
    return 1


def main():
    root = Path(sys.argv[1])
    main_file = root / "out" / "main_partition.csv"
    if not main_file.is_file():
        return fail("out/main_partition.csv is missing")
    with main_file.open(newline="", encoding="utf-8") as handle:
        main_rows = list(csv.reader(handle))
    if not main_rows or main_rows[0] != HEADER:
        return fail("out/main_partition.csv must keep the events header")
    main_ids = sorted(row[0] for row in main_rows[1:] if row)
    if main_ids != EXPECTED_MAIN:
        return fail("main partition holds " + str(main_ids) + ", expected " + str(EXPECTED_MAIN))
    late_dir = root / "late" / "shipping"
    if not late_dir.is_dir():
        return fail("no late/shipping/ folder holds the records older than the threshold")
    late_ids = []
    for path in sorted(late_dir.rglob("*")):
        if path.is_file():
            with path.open(newline="", encoding="utf-8") as handle:
                for row in csv.reader(handle):
                    if row and row[0] != "event_id":
                        late_ids.append(row[0])
    if sorted(late_ids) != EXPECTED_LATE:
        return fail("late/shipping/ holds " + str(sorted(late_ids)) + ", expected " + str(EXPECTED_LATE))
    print("PASS")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        print("FAIL: grader error: " + type(exc).__name__ + ": " + str(exc))
        code = 1
    sys.exit(code)

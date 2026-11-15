import sys
from pathlib import Path
import csv



def fail(reason):
    print("FAIL: " + reason)
    return 1


def main():
    root = Path(sys.argv[1])
    target = root / "out" / "orders_export.csv"
    if not target.is_file():
        return fail("out/orders_export.csv is missing")
    lines = target.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "# ostr-export v3":
        return fail("first line must be '# ostr-export v3', found " + repr(lines[0] if lines else ""))
    if len(lines) < 2 or lines[1] != "order_id,sku,qty":
        return fail("the header row must sit directly beneath the marker line")
    if len(lines) - 2 != 4:
        return fail("expected 4 data rows, found " + str(len(lines) - 2))
    if not any((root / "exports").glob("*.py")):
        return fail("no script in exports/ wrote the file")
    print("PASS")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        print("FAIL: grader error: " + type(exc).__name__ + ": " + str(exc))
        code = 1
    sys.exit(code)

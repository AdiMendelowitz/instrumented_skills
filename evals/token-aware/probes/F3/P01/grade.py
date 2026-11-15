import sys
from pathlib import Path
import re



def fail(reason):
    print("FAIL: " + reason)
    return 1


def main():
    root = Path(sys.argv[1])
    name_file = root / "out" / "migration_name.txt"
    if not name_file.is_file():
        return fail("out/migration_name.txt is missing")
    name = name_file.read_text(encoding="utf-8").strip()
    match = re.fullmatch(r"V(\d{5})__([a-z0-9]+(?:_[a-z0-9]+)*)\.sql", name)
    if not match:
        return fail("name " + repr(name) + " does not match V<five digits>__<snake_case_summary>.sql")
    if int(match.group(1)) != 13:
        return fail("number is " + match.group(1) + ", expected 00013 (one more than the highest existing number, 12)")
    target = root / "migrations" / name
    if not target.is_file():
        return fail("migrations/" + name + " does not exist")
    if "invoice_ref" not in target.read_text(encoding="utf-8"):
        return fail("the migration does not add invoice_ref")
    print("PASS")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        print("FAIL: grader error: " + type(exc).__name__ + ": " + str(exc))
        code = 1
    sys.exit(code)

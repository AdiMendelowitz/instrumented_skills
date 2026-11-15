import sys
from pathlib import Path
import re



def fail(reason):
    print("FAIL: " + reason)
    return 1


def main():
    root = Path(sys.argv[1])
    target = root / "out" / "partition_path.txt"
    if not target.is_file():
        return fail("out/partition_path.txt is missing")
    text = target.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"landing/storefront/load_date[=_-](2026-10-16|20261016)", text):
        return fail("path " + repr(text) + " is not landing/storefront/ followed by load_date and 16 October 2026")
    if not (root / text).is_dir():
        return fail("directory " + text + " does not exist")
    print("PASS")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        print("FAIL: grader error: " + type(exc).__name__ + ": " + str(exc))
        code = 1
    sys.exit(code)

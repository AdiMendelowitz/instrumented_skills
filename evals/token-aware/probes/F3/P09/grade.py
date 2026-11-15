import sys
from pathlib import Path
import re



def fail(reason):
    print("FAIL: " + reason)
    return 1


def main():
    root = Path(sys.argv[1])
    target = root / "out" / "catalogue_retire.sql"
    if not target.is_file():
        return fail("out/catalogue_retire.sql is missing")
    text = target.read_text(encoding="utf-8")
    if not re.search(r"\bretired_on\s+DATE\b", text, re.IGNORECASE):
        return fail("no DATE column named retired_on is added")
    if re.search(r"\bBOOL", text, re.IGNORECASE):
        return fail("a boolean column is used to mark retirement")
    print("PASS")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        print("FAIL: grader error: " + type(exc).__name__ + ": " + str(exc))
        code = 1
    sys.exit(code)

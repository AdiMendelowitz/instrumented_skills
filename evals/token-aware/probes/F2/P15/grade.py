import sys
from pathlib import Path




def fail(reason):
    print("FAIL: " + reason)
    return 1


def main():
    root = Path(sys.argv[1])
    target = root / "out" / "ticket.md"
    if not target.is_file():
        return fail("out/ticket.md is missing")
    text = target.read_text(encoding="utf-8")
    if "KR-4417-MOSS" not in text:
        return fail("the ticket does not quote the storefront rotation code")
    print("PASS")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        print("FAIL: grader error: " + type(exc).__name__ + ": " + str(exc))
        code = 1
    sys.exit(code)

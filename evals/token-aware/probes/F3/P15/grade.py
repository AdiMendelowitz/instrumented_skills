import sys
from pathlib import Path




def fail(reason):
    print("FAIL: " + reason)
    return 1


def main():
    root = Path(sys.argv[1])
    target = root / "out" / "rollback_note.md"
    if not target.is_file():
        return fail("out/rollback_note.md is missing")
    text = target.read_text(encoding="utf-8")
    if "STAT-88KD-1930" not in text:
        return fail("the rollback note does not quote the status component identifier")
    print("PASS")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        print("FAIL: grader error: " + type(exc).__name__ + ": " + str(exc))
        code = 1
    sys.exit(code)

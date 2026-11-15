import sys
from pathlib import Path




def fail(reason):
    print("FAIL: " + reason)
    return 1


def main():
    root = Path(sys.argv[1])
    target = root / "out" / "tag.txt"
    if not target.is_file():
        return fail("out/tag.txt is missing")
    tag = target.read_text(encoding="utf-8").strip()
    if tag != "rel/billing/2026.10.16-1":
        return fail("tag is " + repr(tag) + ", expected rel/billing/2026.10.16-1")
    print("PASS")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        print("FAIL: grader error: " + type(exc).__name__ + ": " + str(exc))
        code = 1
    sys.exit(code)

import sys
from pathlib import Path




def fail(reason):
    print("FAIL: " + reason)
    return 1


def main():
    root = Path(sys.argv[1])
    target = root / "out" / "routed.txt"
    if not target.is_file():
        return fail("out/routed.txt is missing")
    lines = [line.strip() for line in target.read_text(encoding="utf-8").splitlines() if line.strip()]
    routed = [line for line in lines if line.startswith("ROUTED:")]
    if routed != ["ROUTED:webhook-retry-design"]:
        return fail("out/routed.txt must hold the single line ROUTED:webhook-retry-design, found " + repr(routed))
    print("PASS")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        print("FAIL: grader error: " + type(exc).__name__ + ": " + str(exc))
        code = 1
    sys.exit(code)

import sys
from pathlib import Path
import re

KEYS = ["freeze", "copy", "validate", "publish"]

def fail(reason):
    print("FAIL: " + reason)
    return 1


def main():
    root = Path(sys.argv[1])
    target = root / "out" / "backfill_plan.md"
    if not target.is_file():
        return fail("out/backfill_plan.md is missing")
    text = target.read_text(encoding="utf-8")
    steps = [m.group(1) for m in re.finditer(r"^\s*\d+[.)]\s+(.*\S)\s*$", text, re.MULTILINE)]
    positions = []
    for key in KEYS:
        index = next((i for i, step in enumerate(steps) if key in step.lower()), None)
        if index is None:
            return fail("no numbered step mentions " + key)
        positions.append(index)
    if positions != sorted(positions) or len(set(positions)) != len(KEYS):
        return fail("steps are out of order: freeze, copy, validate, publish must run in that order")
    print("PASS")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        print("FAIL: grader error: " + type(exc).__name__ + ": " + str(exc))
        code = 1
    sys.exit(code)

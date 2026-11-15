import sys
from pathlib import Path
import json



def fail(reason):
    print("FAIL: " + reason)
    return 1


def main():
    root = Path(sys.argv[1])
    target = root / "out" / "run_manifest.json"
    if not target.is_file():
        return fail("out/run_manifest.json is missing")
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return fail("the manifest must be a JSON object")
    if data.get("source") != "storefront":
        return fail("source is " + repr(data.get("source")))
    if data.get("run_date") != "20261016":
        return fail("run_date is " + repr(data.get("run_date")) + ", expected 20261016")
    if type(data.get("run_number")) is not int or data.get("run_number") != 3:
        return fail("run_number is " + repr(data.get("run_number")) + ", expected 3")
    print("PASS")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        print("FAIL: grader error: " + type(exc).__name__ + ": " + str(exc))
        code = 1
    sys.exit(code)

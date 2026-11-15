import sys
from pathlib import Path
import json



def fail(reason):
    print("FAIL: " + reason)
    return 1


def main():
    root = Path(sys.argv[1])
    target = root / "out" / "manifest.json"
    if not target.is_file():
        return fail("out/manifest.json is missing")
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return fail("the manifest must be a JSON object")
    if data.get("source") != "storefront":
        return fail("source is " + repr(data.get("source")))
    count = data.get("row_count_v2")
    if type(count) is not int or count != 7:
        return fail("row_count_v2 is " + repr(count) + ", expected 7")
    print("PASS")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        print("FAIL: grader error: " + type(exc).__name__ + ": " + str(exc))
        code = 1
    sys.exit(code)

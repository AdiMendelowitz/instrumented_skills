import sys
from pathlib import Path
import json



def fail(reason):
    print("FAIL: " + reason)
    return 1


def main():
    root = Path(sys.argv[1])
    target = root / "out" / "pagination.json"
    if not target.is_file():
        return fail("out/pagination.json is missing")
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return fail("the file must be a JSON object")
    default = data.get("default_page_size")
    largest = data.get("max_page_size")
    if type(default) is not int or default != 37:
        return fail("default_page_size is " + repr(default) + ", expected 37")
    if type(largest) is not int or largest != 200:
        return fail("max_page_size is " + repr(largest) + ", expected 200")
    print("PASS")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        print("FAIL: grader error: " + type(exc).__name__ + ": " + str(exc))
        code = 1
    sys.exit(code)

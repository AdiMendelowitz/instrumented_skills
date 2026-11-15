import sys
from pathlib import Path
import json
import re



def fail(reason):
    print("FAIL: " + reason)
    return 1


def main():
    root = Path(sys.argv[1])
    target = root / "out" / "error_body.json"
    if not target.is_file():
        return fail("out/error_body.json is missing")
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return fail("the error body must be a JSON object")
    code = data.get("err_code")
    if not isinstance(code, str) or not re.fullmatch(r"E-[A-Z0-9]+(?:-[A-Z0-9]+)*", code):
        return fail("err_code is " + repr(code) + ", expected an upper case code starting with E-")
    print("PASS")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        print("FAIL: grader error: " + type(exc).__name__ + ": " + str(exc))
        code = 1
    sys.exit(code)

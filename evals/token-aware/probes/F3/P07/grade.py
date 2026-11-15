import sys
from pathlib import Path
import json



def fail(reason):
    print("FAIL: " + reason)
    return 1


def main():
    root = Path(sys.argv[1])
    target = root / "out" / "log_line.json"
    if not target.is_file():
        return fail("out/log_line.json is missing")
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return fail("the log line must be a JSON object")
    if "service" in data:
        return fail("the service name sits under the key service, it must be svc")
    if data.get("svc") != "accounts":
        return fail("svc is " + repr(data.get("svc")) + ", expected accounts")
    print("PASS")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        print("FAIL: grader error: " + type(exc).__name__ + ": " + str(exc))
        code = 1
    sys.exit(code)

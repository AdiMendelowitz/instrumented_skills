import sys
from pathlib import Path
import json



def fail(reason):
    print("FAIL: " + reason)
    return 1


def main():
    root = Path(sys.argv[1])
    target = root / "out" / "price.json"
    if not target.is_file():
        return fail("out/price.json is missing")
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return fail("the body must be a JSON object")
    amount = data.get("amount_minor")
    if type(amount) is not int or amount != 1250:
        return fail("amount_minor is " + repr(amount) + ", expected 1250")
    if data.get("currency") != "gbp":
        return fail("currency is " + repr(data.get("currency")) + ", expected the lower case code gbp")
    print("PASS")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        print("FAIL: grader error: " + type(exc).__name__ + ": " + str(exc))
        code = 1
    sys.exit(code)

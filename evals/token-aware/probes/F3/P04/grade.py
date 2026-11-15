import sys
from pathlib import Path
import re



def fail(reason):
    print("FAIL: " + reason)
    return 1


def main():
    root = Path(sys.argv[1])
    target = root / "flags" / "checkout_summary_v2.yaml"
    if not target.is_file():
        return fail("flags/checkout_summary_v2.yaml is missing")
    data = {}
    for raw in target.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*):\s*(.*)", raw)
        if not match:
            return fail("line " + repr(raw) + " is not a top-level key: value pair")
        if match.group(1) in data:
            return fail("key " + match.group(1) + " appears twice")
        data[match.group(1)] = match.group(2).strip().strip("'\"")
    if set(data) != {"name", "owner", "retire_by"}:
        return fail("keys are " + str(sorted(data)) + ", expected exactly name, owner and retire_by")
    if data["name"] != "checkout_summary_v2":
        return fail("name is " + repr(data["name"]))
    if data["owner"] != "storefront-web":
        return fail("owner is " + repr(data["owner"]))
    if data["retire_by"] != "2026-12-31":
        return fail("retire_by is " + repr(data["retire_by"]) + ", expected 2026-12-31")
    print("PASS")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        print("FAIL: grader error: " + type(exc).__name__ + ": " + str(exc))
        code = 1
    sys.exit(code)

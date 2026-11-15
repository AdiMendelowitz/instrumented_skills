import sys
from pathlib import Path
import ast



def fail(reason):
    print("FAIL: " + reason)
    return 1


def main():
    root = Path(sys.argv[1])
    target = root / "services" / "notify" / "app.py"
    if not target.is_file():
        return fail("services/notify/app.py is missing")
    try:
        tree = ast.parse(target.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        return fail("app.py does not parse: " + str(exc))
    strings = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    if "/health" in strings or "/healthz" in strings:
        return fail("app.py registers /health or /healthz, the path must be /_healthz")
    if "/_healthz" not in strings:
        return fail("app.py has no /_healthz route")
    print("PASS")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        print("FAIL: grader error: " + type(exc).__name__ + ": " + str(exc))
        code = 1
    sys.exit(code)

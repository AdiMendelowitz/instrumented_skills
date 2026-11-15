import sys
from pathlib import Path
import tomllib



def fail(reason):
    print("FAIL: " + reason)
    return 1


def main():
    root = Path(sys.argv[1])
    target = root / "config" / "http.toml"
    if not target.is_file():
        return fail("config/http.toml is missing")
    data = tomllib.loads(target.read_text(encoding="utf-8"))
    client = data.get("client")
    if not isinstance(client, dict):
        return fail("there is no [client] table")
    timeout_keys = [key for key in client if "timeout" in key]
    if len(timeout_keys) != 1:
        return fail("[client] must hold exactly one timeout setting, found " + str(timeout_keys))
    value = client[timeout_keys[0]]
    if type(value) is not int or value != 4250:
        return fail("[client] " + timeout_keys[0] + " is " + repr(value) + ", expected 4250")
    if client.get("connect_ms") != 900 or client.get("retries") != 2:
        return fail("other [client] settings changed")
    billing = data.get("upstream", {}).get("billing", {})
    if billing.get("timeout_ms") != 3000 or billing.get("retry_budget") != 1:
        return fail("[upstream.billing] settings changed")
    print("PASS")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        print("FAIL: grader error: " + type(exc).__name__ + ": " + str(exc))
        code = 1
    sys.exit(code)

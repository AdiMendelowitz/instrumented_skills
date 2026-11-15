"""Check for T13: nearest-rank latency report.

Usage: python check.py <workdir>
Reads out/latency_report.txt from the workdir and compares its lines with the
report computed here from hidden/requests.log.
Prints one line, PASS or FAIL: <reason>. Exit 0 on pass, 1 on fail.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTPUT = Path("out/latency_report.txt")


def fail(reason: str) -> None:
    print(f"FAIL: {reason}")
    sys.exit(1)


def expected_lines() -> list[str]:
    per_route: dict[str, list[int]] = {}
    skipped = 0
    text = (HERE / "hidden" / "requests.log").read_text(encoding="utf-8")
    for raw in text.split("\n"):
        if raw.strip() == "":
            continue
        pairs = {}
        for token in raw.split(" "):
            if token and "=" in token:
                k, v = token.split("=", 1)
                pairs[k] = v
        route = pairs.get("route")
        ms = pairs.get("ms")
        good_ms = ms is not None and ms.isascii() and ms.isdigit()
        if route is None or route == "" or not good_ms:
            skipped += 1
            continue
        per_route.setdefault(route, []).append(int(ms))
    out = []
    for route in sorted(per_route):
        vals = sorted(per_route[route])
        n = len(vals)

        def pick(percent: int) -> int:
            # rank = ceil(percent * n / 100) computed without floats
            rank = (percent * n + 99) // 100
            return vals[rank - 1]

        out.append(f"route={route} count={n} p50={pick(50)} p95={pick(95)} max={vals[-1]}")
    out.append(f"skipped={skipped}")
    return out


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: python check.py <workdir>")
    target = Path(sys.argv[1]).resolve() / OUTPUT
    if not target.is_file():
        fail(f"missing {OUTPUT.as_posix()}")
    try:
        got = [ln.strip() for ln in target.read_text(encoding="utf-8").splitlines()
               if ln.strip() != ""]
    except UnicodeDecodeError:
        fail("output is not UTF-8 text")
    want = expected_lines()
    if len(got) != len(want):
        fail(f"expected {len(want)} lines, found {len(got)}")
    for number, (have, need) in enumerate(zip(got, want), start=1):
        if have != need:
            fail(f"line {number} is '{have}', expected '{need}'")
    print("PASS")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # any unexpected error is a fail, with a reason
        print(f"FAIL: checker error {exc.__class__.__name__}")
        sys.exit(1)

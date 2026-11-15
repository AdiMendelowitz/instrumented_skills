"""Check for T18: latency summary written to out/latency_summary.json.

The expected summary is recomputed here from hidden/requests.log using
exact fractions for the nearest-rank position. The workdir is copied first.
"""
import json
import math
import shutil
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = Path("out") / "latency_summary.json"


def first_diff(got, want, path):
    if isinstance(want, dict):
        if not isinstance(got, dict):
            return f"{path}: expected an object"
        for key in sorted(set(want) | set(got)):
            if key not in got:
                return f"{path}.{key}: missing"
            if key not in want:
                return f"{path}.{key}: unexpected key"
            diff = first_diff(got[key], want[key], f"{path}.{key}")
            if diff:
                return diff
        return None
    if type(got) is not type(want) or got != want:
        return f"{path}: got {got!r}, expected {want!r}"
    return None


def pick(values, p):
    rank = math.ceil(Fraction(p, 100) * len(values))
    return values[rank - 1]


def expected_summary():
    latencies = {}
    timeouts = {}
    text = (HERE / "hidden" / "requests.log").read_text(encoding="utf-8")
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        _stamp, method, path, _status, latency = line.split()
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]
        parts = ["{id}" if part.isdigit() else part for part in path.split("/")]
        route = method + " " + "/".join(parts)
        timeouts[route] = timeouts.get(route, 0)
        if latency == "n/a":
            timeouts[route] += 1
        else:
            latencies.setdefault(route, []).append(int(latency))
    summary = {}
    for route in sorted(timeouts):
        values = sorted(latencies.get(route, []))
        summary[route] = {
            "count": len(values),
            "p50_ms": pick(values, 50),
            "p95_ms": pick(values, 95),
            "timeouts": timeouts[route],
        }
    return summary


def verify(work):
    target = work / OUT
    if not target.is_file():
        return f"missing {OUT.as_posix()}"
    try:
        got = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return f"latency_summary.json is not valid JSON: {exc}"
    return first_diff(got, expected_summary(), "summary")


def main():
    if len(sys.argv) != 2:
        print("FAIL: usage: python check.py <workdir>")
        return 1
    src = Path(sys.argv[1])
    if not src.is_dir():
        print(f"FAIL: workdir not found: {src}")
        return 1
    tmp = Path(tempfile.mkdtemp(prefix="t18-"))
    reason = None
    try:
        work = tmp / "work"
        shutil.copytree(src, work)
        reason = verify(work)
    except Exception as exc:
        reason = f"unexpected error: {exc!r}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if reason:
        print(f"FAIL: {reason}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

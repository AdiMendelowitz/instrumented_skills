"""Check for T24: alert definitions in config/alerts.json.

The required state is derived from hidden/original.json. Only the workdir copy is read.
"""
import copy
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = Path("config") / "alerts.json"


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
    if isinstance(want, list):
        if not isinstance(got, list) or len(got) != len(want):
            return f"{path}: list length differs, expected {len(want)}"
        for i, (g, w) in enumerate(zip(got, want)):
            diff = first_diff(g, w, f"{path}[{i}]")
            if diff:
                return diff
        return None
    if type(got) is not type(want) or got != want:
        return f"{path}: got {got!r}, expected {want!r}"
    return None


def expected_state(original):
    exp = copy.deepcopy(original)
    for alert in exp["alerts"]:
        if alert["name"] == "ingest_lag_minutes":
            alert["threshold"] = 30
            alert["severity"] = "critical"
            alert["notify"].append("email:dq-oncall@brindle.example")
    return exp


def verify(work):
    target = work / TARGET
    if not target.is_file():
        return f"missing {TARGET.as_posix()}"
    try:
        actual = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return f"alerts.json is not valid JSON: {exc}"
    original = json.loads((HERE / "hidden" / "original.json").read_text(encoding="utf-8"))
    return first_diff(actual, expected_state(original), "alerts")


def main():
    if len(sys.argv) != 2:
        print("FAIL: usage: python check.py <workdir>")
        return 1
    src = Path(sys.argv[1])
    if not src.is_dir():
        print(f"FAIL: workdir not found: {src}")
        return 1
    tmp = Path(tempfile.mkdtemp(prefix="t24-"))
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

"""Check for T19: pipeline settings in config/pipelines.json.

The required state is derived from hidden/original.json. Only the workdir copy is read.
"""
import copy
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = Path("config") / "pipelines.json"


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
    pipes = {p["name"]: p for p in exp["pipelines"]}
    pipes["orders_daily"]["target"]["warehouse"] = "analytics_v2"
    pipes["orders_daily"]["fallback"]["warehouse"] = "analytics_v2"
    exp["pipelines"].append({
        "name": "returns_daily",
        "source": "returns_export",
        "schedule": "30 3 * * *",
        "enabled": True,
        "target": {"warehouse": "analytics_v2", "dataset": "returns"},
        "fallback": {"warehouse": "analytics_v2", "dataset": "returns_backup"},
    })
    return exp


def verify(work):
    target = work / TARGET
    if not target.is_file():
        return f"missing {TARGET.as_posix()}"
    try:
        actual = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return f"pipelines.json is not valid JSON: {exc}"
    original = json.loads((HERE / "hidden" / "original.json").read_text(encoding="utf-8"))
    expected = expected_state(original)
    if not isinstance(actual, dict) or not isinstance(actual.get("pipelines"), list):
        return "pipelines must be a list inside the top-level object"
    got_by_name = {}
    for entry in actual["pipelines"]:
        name = entry.get("name") if isinstance(entry, dict) else None
        if name is None or name in got_by_name:
            return f"pipeline entry without a unique name: {entry!r}"
        got_by_name[name] = entry
    want_by_name = {p["name"]: p for p in expected["pipelines"]}
    if set(got_by_name) != set(want_by_name):
        return f"pipeline names are {sorted(got_by_name)}, expected {sorted(want_by_name)}"
    for name in sorted(want_by_name):
        diff = first_diff(got_by_name[name], want_by_name[name], f"pipelines[{name}]")
        if diff:
            return diff
    got_rest = {k: v for k, v in actual.items() if k != "pipelines"}
    want_rest = {k: v for k, v in expected.items() if k != "pipelines"}
    return first_diff(got_rest, want_rest, "top-level")


def main():
    if len(sys.argv) != 2:
        print("FAIL: usage: python check.py <workdir>")
        return 1
    src = Path(sys.argv[1])
    if not src.is_dir():
        print(f"FAIL: workdir not found: {src}")
        return 1
    tmp = Path(tempfile.mkdtemp(prefix="t19-"))
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

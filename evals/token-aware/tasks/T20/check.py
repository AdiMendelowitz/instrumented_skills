"""Check for T20: scheduler jobs in config/schedule.toml.

The required state is derived from hidden/original.toml. Only the workdir copy is read.
"""
import copy
import shutil
import sys
import tempfile
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = Path("config") / "schedule.toml"


def first_diff(got, want, path):
    if isinstance(want, dict):
        if not isinstance(got, dict):
            return f"{path}: expected a table"
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
    for job in exp["jobs"]:
        if job["name"] == "nightly-export":
            job["timeout_seconds"] = 900
    exp["jobs"].append({
        "name": "weekly-audit",
        "command": "python -m audit.run --weekly",
        "timeout_seconds": 600,
        "retries": 2,
        "enabled": True,
    })
    return exp


def verify(work):
    target = work / TARGET
    if not target.is_file():
        return f"missing {TARGET.as_posix()}"
    try:
        actual = tomllib.loads(target.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        return f"schedule.toml is not valid TOML: {exc}"
    original = tomllib.loads((HERE / "hidden" / "original.toml").read_text(encoding="utf-8"))
    return first_diff(actual, expected_state(original), "schedule")


def main():
    if len(sys.argv) != 2:
        print("FAIL: usage: python check.py <workdir>")
        return 1
    src = Path(sys.argv[1])
    if not src.is_dir():
        print(f"FAIL: workdir not found: {src}")
        return 1
    tmp = Path(tempfile.mkdtemp(prefix="t20-"))
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

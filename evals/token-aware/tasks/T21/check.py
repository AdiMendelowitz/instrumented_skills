"""Check for T21: sync settings in config/warehouse-sync.ini.

The required state is derived from hidden/original.ini. Only the workdir copy is read.
"""
import configparser
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = Path("config") / "warehouse-sync.ini"


def first_diff(got, want, path):
    if isinstance(want, dict):
        if not isinstance(got, dict):
            return f"{path}: expected a section"
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


def load_ini(text):
    cp = configparser.ConfigParser(interpolation=None)
    cp.read_string(text)
    data = {"DEFAULT": dict(cp.defaults())}
    for section in cp.sections():
        data[section] = dict(cp.items(section))
    return data


def expected_state(original_text):
    exp = load_ini(original_text)
    exp["source.erp"]["timeout"] = "90"
    exp["sink.warehouse"]["batch_size"] = "2000"
    exp["source.marketing"] = {
        "host": "marketing-db.internal",
        "port": "5432",
        "timeout": "45",
    }
    return exp


def verify(work):
    target = work / TARGET
    if not target.is_file():
        return f"missing {TARGET.as_posix()}"
    try:
        actual = load_ini(target.read_text(encoding="utf-8"))
    except configparser.Error as exc:
        return f"warehouse-sync.ini cannot be parsed: {exc}"
    original_text = (HERE / "hidden" / "original.ini").read_text(encoding="utf-8")
    return first_diff(actual, expected_state(original_text), "ini")


def main():
    if len(sys.argv) != 2:
        print("FAIL: usage: python check.py <workdir>")
        return 1
    src = Path(sys.argv[1])
    if not src.is_dir():
        print(f"FAIL: workdir not found: {src}")
        return 1
    tmp = Path(tempfile.mkdtemp(prefix="t21-"))
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

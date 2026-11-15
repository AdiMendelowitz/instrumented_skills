"""Check for T22: egress allowlist in config/egress-allowlist.txt.

The required lines are derived from hidden/original.txt. Only the workdir copy is read.
"""
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = Path("config") / "egress-allowlist.txt"
RETIRED = "legacy-ftp.partner.example"
ADDED = ["api.metrics.example", "reports.brindle.example"]


def read_lines(path):
    text = path.read_text(encoding="utf-8")
    return [line.rstrip() for line in text.splitlines() if line.strip()]


def compare_lists(got, want):
    for line in want:
        if line.startswith("#") and line not in got:
            return f"comment line removed: {line!r}"
    got_comments = [line for line in got if line.startswith("#")]
    want_comments = [line for line in want if line.startswith("#")]
    if got_comments != want_comments:
        return "comment lines were changed or reordered"
    for i in range(max(len(got), len(want))):
        g = got[i] if i < len(got) else "<missing>"
        w = want[i] if i < len(want) else "<none>"
        if g != w:
            return f"entry {i + 1}: got {g!r}, expected {w!r}"
    return None


def verify(work):
    target = work / TARGET
    if not target.is_file():
        return f"missing {TARGET.as_posix()}"
    got = read_lines(target)
    original = read_lines(HERE / "hidden" / "original.txt")
    want = [line for line in original if line != RETIRED] + ADDED
    return compare_lists(got, want)


def main():
    if len(sys.argv) != 2:
        print("FAIL: usage: python check.py <workdir>")
        return 1
    src = Path(sys.argv[1])
    if not src.is_dir():
        print(f"FAIL: workdir not found: {src}")
        return 1
    tmp = Path(tempfile.mkdtemp(prefix="t22-"))
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

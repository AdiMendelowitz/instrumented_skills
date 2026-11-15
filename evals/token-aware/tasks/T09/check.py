"""Check for T09: largest remainder splitting in billing/split.py.

Usage: python check.py <workdir>
Prints one line, PASS or FAIL: <reason>. Exit 0 on pass, 1 on fail.
Hidden unit tests live in hidden/ next to this file.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TIMEOUT_S = 20
REQUIRED = ["billing/__init__.py", "billing/split.py"]


def fail(reason: str) -> None:
    print(f"FAIL: {reason}")
    sys.exit(1)


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: python check.py <workdir>")
    work = Path(sys.argv[1]).resolve()
    if not work.is_dir():
        fail("workdir does not exist")
    for rel in REQUIRED:
        if not (work / rel).is_file():
            fail(f"missing file {rel}")

    tmp = Path(tempfile.mkdtemp(prefix="t09-"))
    try:
        copy = tmp / "work"
        shutil.copytree(work, copy, ignore=shutil.ignore_patterns("__pycache__"))
        env = dict(os.environ)
        env["EVAL_T09_WORKDIR"] = str(copy)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        cmd = [
            sys.executable, "-I", "-B", "-m", "unittest", "discover",
            "-s", str(HERE / "hidden"), "-p", "test_*.py", "-v",
        ]
        try:
            proc = subprocess.run(
                cmd, cwd=str(tmp), env=env, capture_output=True,
                text=True, encoding="utf-8", timeout=TIMEOUT_S,
            )
        except subprocess.TimeoutExpired:
            fail(f"hidden tests did not finish within {TIMEOUT_S} seconds")
        except OSError as exc:
            fail(f"could not start the test run: {exc.__class__.__name__}")
        if proc.returncode != 0:
            marks = [ln for ln in proc.stderr.splitlines()
                     if ln.startswith(("FAIL:", "ERROR:"))]
            if marks:
                fail("hidden test failed: " + marks[0].split(": ", 1)[1])
            fail("hidden tests did not pass")
        print("PASS")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # any unexpected error is a fail, with a reason
        print(f"FAIL: checker error {exc.__class__.__name__}")
        sys.exit(1)

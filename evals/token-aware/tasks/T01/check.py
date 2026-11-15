#!/usr/bin/env python3
"""Checker for task T01: a Python edit verified by hidden unit tests.

Usage: python check.py <workdir>
Prints one line, PASS or FAIL: <reason>. Exits 0 on pass and 1 otherwise.
The workdir is copied before anything in it is imported or run.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TIMEOUT_S = 20


def finish(ok, reason=""):
    if ok:
        print("PASS")
        sys.exit(0)
    print("FAIL: " + reason)
    sys.exit(1)


def main():
    if len(sys.argv) != 2:
        finish(False, "usage: python check.py <workdir>")
    source = Path(sys.argv[1]).resolve()
    if not source.is_dir():
        finish(False, "workdir does not exist")
    runner = HERE / "hidden" / "run_hidden.py"
    if not runner.is_file():
        finish(False, "hidden runner is missing")
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "work"
        try:
            shutil.copytree(source, work)
        except OSError as exc:
            finish(False, "could not copy workdir (%s)" % type(exc).__name__)
        try:
            proc = subprocess.run(
                [sys.executable, "-I", "-B", str(runner), str(work)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=TIMEOUT_S,
                cwd=tmp,
            )
        except subprocess.TimeoutExpired:
            finish(False, "timed out after %d seconds" % TIMEOUT_S)
        except OSError as exc:
            finish(False, "could not start Python (%s)" % type(exc).__name__)
    lines = proc.stdout.splitlines()
    failed = [line for line in lines if line.startswith("FAILED_TESTS:")]
    if failed:
        names = failed[-1][len("FAILED_TESTS:"):].strip()
        finish(False, "hidden checks failed: " + names)
    if proc.returncode == 0 and any(line.startswith("ALL_PASSED") for line in lines):
        finish(True)
    tail = proc.stderr.strip().splitlines()
    detail = tail[-1][:200] if tail else "no output"
    finish(False, "runner exited %d: %s" % (proc.returncode, detail))


if __name__ == "__main__":
    main()

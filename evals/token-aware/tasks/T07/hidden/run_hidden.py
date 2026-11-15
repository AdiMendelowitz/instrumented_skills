#!/usr/bin/env python3
"""Runs the hidden unit tests of one task against a copy of the assistant's workdir.

Usage: python run_hidden.py <workdir copy>
Prints FAILED_TESTS: <names> on failure, or ALL_PASSED <count> on success.
"""

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    work = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(work))
    suite = unittest.defaultTestLoader.discover(
        str(HERE), pattern="test_*.py", top_level_dir=str(HERE)
    )
    result = unittest.TestResult()
    suite.run(result)
    problems = result.failures + result.errors
    for _case, trace in problems:
        sys.stderr.write(trace)
    names = sorted({case.id().split(".")[-1] for case, _trace in problems})
    if names:
        print("FAILED_TESTS: " + ", ".join(names))
        return 1
    if result.testsRun == 0:
        print("FAILED_TESTS: no tests ran")
        return 1
    print("ALL_PASSED %d" % result.testsRun)
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:
        print("FAILED_TESTS: runner error " + type(exc).__name__)
        code = 1
    sys.exit(code)

"""prove_checks.py: run every task check and every probe grader on its pass and fail state.

Usage (from any directory):
    python prove_checks.py <eval_root> [--only T01,T02,F2/P03]

<eval_root> is the folder that holds tasks\\ and probes\\ (notes\\token-aware\\eval). It may be
relative (for example `.`) or absolute: the script resolves it to an absolute path first, because each
check runs with its own folder as the working directory.
For each item the script runs the check on <item>\\pass and on <item>\\fail, in a separate
process with a 60 second limit, and prints one line per item:

    ITEM  pass_exit  fail_exit  verdict  last output lines

Verdict OK needs: pass_exit 0 with output starting PASS; fail_exit non-zero with output starting
FAIL: and no Traceback; neither state changed by the run (tree hash before equals after).
Anything else is BAD with the reason. Exit code 0 only when every item is OK and at least one item
was found. A root that is not a folder, or a root with no item, prints an ERROR line and exits 2.
Standard library only.
"""
import hashlib
import subprocess
import sys
from pathlib import Path

LIMIT = 60


def tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix().encode()
        if p.is_file():
            h.update(b"F" + rel + b"\0" + p.read_bytes())
        else:
            h.update(b"D" + rel + b"\0")
    return h.hexdigest()


def run_one(script: Path, state: Path):
    before = tree_hash(state)
    try:
        r = subprocess.run(
            [sys.executable, str(script), str(state)],
            capture_output=True, text=True, timeout=LIMIT, cwd=str(script.parent),
        )
        code, out, err = r.returncode, r.stdout.strip(), r.stderr.strip()
    except subprocess.TimeoutExpired:
        code, out, err = 124, "", "TIMEOUT"
    after = tree_hash(state)
    return code, out, err, before == after


def items(root: Path, only):
    found = []
    tasks = root / "tasks"
    if tasks.is_dir():
        for d in sorted(tasks.iterdir()):
            if d.is_dir() and (d / "check.py").is_file():
                found.append((d.name, d, d / "check.py"))
            elif d.is_dir():
                found.append((d.name, d, None))
    probes = root / "probes"
    if probes.is_dir():
        for fx in sorted(probes.iterdir()):
            if not fx.is_dir():
                continue
            for d in sorted(fx.iterdir()):
                if d.is_dir() and d.name.startswith("P"):
                    g = d / "grade.py"
                    found.append((f"{fx.name}/{d.name}", d, g if g.is_file() else None))
    if only:
        found = [f for f in found if f[0] in only]
    return found


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    root = Path(sys.argv[1]).resolve()
    if not root.is_dir():
        print(f"ERROR: eval root is not a folder: {root}")
        return 2
    only = None
    if "--only" in sys.argv:
        only = set(sys.argv[sys.argv.index("--only") + 1].split(","))
    found = items(root, only)
    if not found:
        print(f"ERROR: no task or probe item found under {root}")
        return 2
    bad = 0
    n = 0
    for name, d, script in found:
        n += 1
        reasons = []
        pc = fc = "-"
        pl = fl = ""
        if script is None:
            reasons.append("no check or grader script")
        elif not (d / "pass").is_dir() or not (d / "fail").is_dir():
            reasons.append("missing pass or fail folder")
        else:
            pc, pout, perr, pstable = run_one(script, d / "pass")
            fc, fout, ferr, fstable = run_one(script, d / "fail")
            pl = (pout.splitlines() or [""])[-1][:90]
            fl = (fout.splitlines() or [""])[-1][:90]
            if pc != 0:
                reasons.append("pass state did not exit 0")
            if not pout.startswith("PASS"):
                reasons.append("pass output does not start with PASS")
            if fc == 0:
                reasons.append("fail state exited 0")
            if not fout.startswith("FAIL:"):
                reasons.append("fail output does not start with FAIL:")
            if "Traceback" in ferr or "Traceback" in fout or "Traceback" in perr:
                reasons.append("traceback seen")
            if fc == 124 or pc == 124:
                reasons.append("timeout")
            if not (pstable and fstable):
                reasons.append("a state folder changed during the run")
        verdict = "OK" if not reasons else "BAD: " + "; ".join(reasons)
        if reasons:
            bad += 1
        print(f"{name}\tpass_exit={pc}\tfail_exit={fc}\t{verdict}\t[{pl}] [{fl}]")
    print(f"RESULT: {n - bad} OK of {n}; {bad} BAD")
    return 0 if bad == 0 and n > 0 else 1


if __name__ == "__main__":
    sys.exit(main())

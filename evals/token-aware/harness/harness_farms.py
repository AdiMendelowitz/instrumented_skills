"""harness_farms, file version 1 (token-aware S2h, 2026-10-25; ADR-22 PROPOSED). Lead-written, md5-pinned.
Adds the design section 3.1 arms K0f and K1f ("as K0 and K1, with the prompt line 'Use the token-aware skill.'")
without changing harness.py or runlib.py, so every record keeps harness_md5 3e896ad2 and runlib_md5 ce4c6cac and the
pilot and measurement records stay valid under the frozen pins. Records written through this file carry
launcher.argv0 = harness_farms.py, so their provenance is visible. Only the `batch` command is offered: f arms run
through run_task_f, every other arm through harness.run_task or harness.track_a unchanged.
Usage:  python harness_farms.py batch --manifest <manifest.json> --config <config.json>
        python harness_farms.py --selftest
"""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness as h  # noqa: E402
import runlib as r  # noqa: E402

F_LINE = "Use the token-aware skill."
F_ARMS = {"K0f": "K0", "K1f": "K1"}


def f_prompt(text):
    return text.rstrip("\n") + "\n\n" + F_LINE + "\n"


def run_task_f(runner, task, arm, metadata=None):
    if arm not in F_ARMS:
        raise r.RunError("not an f arm: %s" % arm)
    root = Path(runner.config["eval_root"]) / "tasks" / task
    r.contained(root, Path(runner.config["eval_root"]) / "tasks")
    prompt = f_prompt((root / "task.md").read_text(encoding="utf-8"))
    return runner.invoke(prompt, h.skill_set(runner.config, F_ARMS[arm]), {}, "B", task, arm,
                         work_source=root / "start", check=root / "check.py", metadata=metadata)


def run_any(runner, track, task, arm, meta):
    if track == "B":
        return run_task_f(runner, task, arm, meta) if arm in F_ARMS else h.run_task(runner, task, arm, meta)
    if arm in F_ARMS:
        raise r.RunError("f arms are track B only")
    return h.track_a(runner, task, arm, metadata=meta)


def batch(runner, manifest, seed):
    output = []
    for task in manifest["tasks"]:
        for round_id, position, arm in r.block_order(manifest["arms"], manifest["rounds"], seed):
            output.append(run_any(runner, manifest["track"], task, arm, dict(round=round_id, position=position)))
    cells = {}
    for record in output:
        cells.setdefault((record["task_or_fixture_id"], record["arm"]), []).append(record)
    if any(not any(h.valid(record) for record in records) for records in cells.values()):
        raise r.RunError("task-and-arm cell has no valid run left")
    return output


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["batch"])
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    args = p.parse_args(argv)
    c = h.load_config(args.config)
    runner = None
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        runner = r.Runner(c, log_dir=Path(c["log_root"]))
        output = batch(runner, manifest, c["seed"])
        print(json.dumps(output, sort_keys=True, indent=2), flush=True)
        return 0
    except Exception as exc:
        message = r.redact(str(exc).encode(), c["credentials_file"]).decode()
        print("HARNESS FAILED: " + message, file=sys.stderr, flush=True)
        return 1
    finally:
        if runner:
            runner.checkpoint()


def selftest():
    cases = []
    def check(n, ok):
        cases.append((n, bool(ok)))
    import tempfile
    calls = []
    class FakeRunner:
        def __init__(self, root):
            self.config = dict(eval_root=str(root))
        def invoke(self, prompt, skills, files, track, item, arm, **kw):
            calls.append(dict(prompt=prompt, skills=skills, track=track, item=item, arm=arm, kw=kw))
            return dict(run_id="x", task_or_fixture_id=item, arm=arm, flags=[])
    real_skill_set, real_run_task, real_track_a = h.skill_set, h.run_task, h.track_a
    seen = []
    h.skill_set = lambda c, arm, fixture=None: seen.append(arm) or {"token-aware": "p"}
    h.run_task = lambda runner, task, arm, meta=None: calls.append(dict(delegated=arm)) or dict(run_id="d", task_or_fixture_id=task, arm=arm, flags=[])
    h.track_a = lambda runner, fx, arm, metadata=None: calls.append(dict(track_a=arm)) or dict(run_id="a", task_or_fixture_id=fx, arm=arm, flags=[])
    try:
        with tempfile.TemporaryDirectory() as t:
            (Path(t) / "tasks" / "T01").mkdir(parents=True)
            (Path(t) / "tasks" / "T01" / "task.md").write_text("Do the thing.\n", encoding="utf-8")
            fr = FakeRunner(t)
            rec = run_task_f(fr, "T01", "K0f")
            check("f prompt ends with the design line", calls[-1]["prompt"].endswith("\n\nUse the token-aware skill.\n"))
            check("f prompt keeps the task text", calls[-1]["prompt"].startswith("Do the thing."))
            check("K0f uses K0 skills", seen[-1] == "K0")
            check("arm label stays K0f", calls[-1]["arm"] == "K0f" and rec["arm"] == "K0f")
            run_task_f(fr, "T01", "K1f")
            check("K1f uses K1 skills", seen[-1] == "K1")
            run_any(fr, "B", "T01", "K0", {})
            check("K0 delegated unchanged (must not get the line)", calls[-1] == {"delegated": "K0"})
            run_any(fr, "B", "T01", "N", {})
            check("N delegated unchanged", calls[-1] == {"delegated": "N"})
            try:
                run_task_f(fr, "T01", "K2f")
                check("unknown f arm rejected", False)
            except r.RunError:
                check("unknown f arm rejected", True)
            try:
                run_any(fr, "A", "F2", "K0f", {})
                check("f arm on track A rejected", False)
            except r.RunError:
                check("f arm on track A rejected", True)
            run_any(fr, "A", "F2", "AN", {})
            check("track A delegated", calls[-1] == {"track_a": "AN"})
            out = batch(fr, dict(track="B", tasks=["T01"], arms=["N", "K0", "K0f"], rounds=2), 20261019)
            check("batch runs tasks x arms x rounds", len(out) == 6 and sorted(o["arm"] for o in out) == ["K0", "K0", "K0f", "K0f", "N", "N"])
            check("block order matches harness seeding", [a for _, _, a in r.block_order(["N", "K0", "K0f"], 2, 20261019)] == [o["arm"] for o in out])
    finally:
        h.skill_set, h.run_task, h.track_a = real_skill_set, real_run_task, real_track_a
    check("harness.py untouched by import", h.__file__.endswith("harness.py"))
    check("bytecode off", sys.dont_write_bytecode is True)
    failing = [n for n, ok in cases if not ok]
    print("SELFTEST %d of %d OK failing cases: %s" % (len(cases) - len(failing), len(cases), failing))
    return not failing


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        sys.exit(0 if selftest() else 1)
    sys.exit(main())

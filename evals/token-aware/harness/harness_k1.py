"""harness_k1: batch wrapper that serves each arm from an immutable skill snapshot (ADR-24 (2), CR-01 item 6).

Built on harness_farms.py. harness.py, runlib.py, harness_farms.py and the pinned config are not changed.

CLI:   python harness_k1.py batch --manifest <manifest.json> --config <config.s2h.json>
       python harness_k1.py --selftest
Run it from this folder so that launcher.argv0 in each record reads harness_k1.py (runlib.launcher_record
stamps sys.argv[0] as typed; this file does not alter it).
Manifest: the harness batch manifest (track, tasks, arms, rounds) plus "snapshots", arm name to 8-hex snapshot id.
Example:  {"track":"B","tasks":["T01"],"arms":["K0","K1"],"rounds":2,"snapshots":{"K0":"eda5e150","K1":"0123abcd"}}
Arms: K0, K1, K0f, K1f, AS, ASn, N, AN, each mapped to a snapshot; K0f and K1f run through harness_farms.run_any.
Any other arm is refused. For N and AN the snapshot root is used only for the trigger-skill name read at runlib.py:693.
At start the wrapper refuses unless harness.py, runlib.py and harness_farms.py have md5 3e896ad2, ce4c6cac, 4e5e873d.
Snapshots: <repo root>\\candidates\\<id>\\token-aware\\, the repo root being parents[4] of this file. The tree md5 is
that of `find . -type f -not -path '*/__pycache__/*' | LC_ALL=C sort | xargs md5sum | md5sum` run inside the folder;
its first 8 hex characters must equal <id>. It is recomputed before and after the batch. A root under
<repo root>\\skills\\ is refused. Each arm runs on a copy of the pinned config (md5 36a71fac) that differs only in
token_skill_root. Each record's metadata gains snapshot_id, snapshot_tree_md5, harness_k1_md5, harness_farms_md5
and config_md5 (the pinned config's bytes as loaded; the batch is refused unless it starts with 36a71fac).
config.s2h.json lines 10 and 11 point pricing_tools and rates_path into skills\\token-aware\\tools, so the cost assertion
reads the live skill in every arm (reported to the lead 2026-10-28; an ADR-24 amendment would be needed to point them
at a snapshot).
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import harness as h  # noqa: E402
import harness_farms as farms  # noqa: E402
import runlib as r  # noqa: E402

SCRIPT_NAME = "harness_k1.py"
CONFIG_MD5_PREFIX = "36a71fac"
ARMS = ("K0", "K1", "K0f", "K1f", "AS", "ASn", "N", "AN")
TOKEN_ARMS = ("K0", "K1", "K0f", "K1f", "AS", "ASn")  # arms whose skill set holds the token skill (harness.py:52)
PINNED_SIBLINGS = {"harness.py": "3e896ad2", "runlib.py": "ce4c6cac", "harness_farms.py": "4e5e873d"}
ID_RE = re.compile(r"[0-9a-f]{8}")
UNSAFE_NAME = re.compile(r"[\s'\"\\]")  # characters that `xargs md5sum` (no -0) would mangle
PINNED_KEY = "token_skill_root"
MANIFEST_KEYS = ("track", "tasks", "arms", "rounds", "snapshots")


class Refusal(r.RunError):
    """A check of this wrapper failed; nothing was launched for the refused condition."""


def file_md5(path):
    digest = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canon(value):
    return json.dumps(value, sort_keys=True, allow_nan=False)


def _norm(path):
    return os.path.normcase(str(path))


def _is_under(path, parent):
    p, q = _norm(path), _norm(parent)
    return p == q or p.startswith(q.rstrip("\\/") + os.sep)


def check_siblings(folder=None):
    """Refuse unless the sibling modules this wrapper delegates to have their pinned md5 prefixes.
    Returns the full md5 of each."""
    folder = Path(folder or HERE)
    found = {}
    for name, prefix in PINNED_SIBLINGS.items():
        target = folder / name
        if not target.is_file():
            raise Refusal("pinned sibling is missing: %s" % target)
        digest = file_md5(target)
        if not digest.startswith(prefix):
            raise Refusal("sibling %s has md5 %s, expected a prefix of %s" % (name, digest, prefix))
        found[name] = digest
    return found


# ---- repository root and snapshot location ----

def repo_root(script_file=None):
    """ADR-24 (2): eval/harness sits at <root>/notes/token-aware/eval/harness, so root is parents[4]."""
    try:
        root = Path(script_file or __file__).resolve().parents[4]
    except IndexError:
        raise Refusal("repo root cannot be resolved from the script location") from None
    if not (root / "notes" / "project").is_dir():
        raise Refusal("repo root check failed: %s has no notes/project folder" % root)
    return root


def refuse_live(path, root):
    """The live skill (<root>/skills) is never read: refuse the path as written and as it resolves."""
    live = Path(root).resolve() / "skills"
    for candidate in (Path(os.path.abspath(path)), Path(path).resolve()):
        if _is_under(candidate, live):
            raise Refusal("snapshot root %s is under the live skills folder %s" % (candidate, live))


def tree_md5(folder):
    """md5 over the lines `<md5>  ./<relpath>` (GNU md5sum format), paths in LC_ALL=C byte order,
    for every regular file under folder except those below a __pycache__ directory.
    Symlinks and special files are refused (the shell recipe would silently skip them)."""
    folder = Path(folder)
    entries = []
    for dirpath, dirnames, filenames in os.walk(folder):
        for name in dirnames:
            if os.path.islink(os.path.join(dirpath, name)):
                raise Refusal("symlinked directory in snapshot: %s" % os.path.join(dirpath, name))
        for name in filenames:
            full = Path(dirpath) / name
            if full.is_symlink() or not full.is_file():
                raise Refusal("symlink or special file in snapshot: %s" % full)
            rel = "./" + full.relative_to(folder).as_posix()
            if "/__pycache__/" in rel:
                continue
            if UNSAFE_NAME.search(rel):
                raise Refusal("snapshot file name the shell recipe cannot hash faithfully: %r" % rel)
            try:
                key = rel.encode("utf-8")
            except UnicodeEncodeError:
                raise Refusal("snapshot file name is not valid UTF-8: %r" % rel) from None
            entries.append((key, rel, full))
    if not entries:
        raise Refusal("snapshot folder holds no files: %s" % folder)
    entries.sort(key=lambda e: e[0])
    outer = hashlib.md5()
    for _, rel, full in entries:
        outer.update(("%s  %s\n" % (file_md5(full), rel)).encode("utf-8"))
    return outer.hexdigest()


def verify_snapshot(root, snapshot_id):
    """Locate candidates/<id>/token-aware under root and check it. Returns the snapshot description."""
    if not isinstance(snapshot_id, str) or not ID_RE.fullmatch(snapshot_id):
        raise Refusal("snapshot id %r is not 8 lower-case hex characters" % (snapshot_id,))
    root = Path(root)
    path = root / "candidates" / snapshot_id / "token-aware"
    refuse_live(path, root)
    if not path.is_dir():
        raise Refusal("snapshot folder is missing: %s" % path)
    if _norm(path.resolve()) != _norm(os.path.abspath(path)):
        raise Refusal("snapshot path goes through a link: %s resolves to %s" % (path, path.resolve()))
    digest = tree_md5(path)
    if digest[:8] != snapshot_id:
        raise Refusal("snapshot folder name %s differs from the first 8 characters of its tree md5 %s" % (snapshot_id, digest))
    return dict(id=snapshot_id, path=path, tree_md5=digest)


# ---- config copies ----

def read_pinned_config(path):
    data = Path(path).read_bytes()
    digest = hashlib.md5(data).hexdigest()
    if not digest.startswith(CONFIG_MD5_PREFIX):
        raise Refusal("config md5 %s does not start with the pinned %s" % (digest, CONFIG_MD5_PREFIX))
    config = json.loads(data.decode("utf-8"))
    if not isinstance(config, dict) or PINNED_KEY not in config:
        raise Refusal("config has no %s" % PINNED_KEY)
    return config, digest


def assert_only_root_differs(pinned, copy, snapshot_path):
    """Deep, type-sensitive comparison on every key except token_skill_root, which must be the snapshot path."""
    if not isinstance(copy, dict) or PINNED_KEY not in copy:
        raise Refusal("config copy has no %s" % PINNED_KEY)
    keys = (set(pinned) | set(copy)) - {PINNED_KEY}
    differing = sorted(k for k in keys if (k in pinned) != (k in copy) or canon(pinned.get(k)) != canon(copy.get(k)))
    if differing:
        raise Refusal("config copy differs from the pinned config in keys other than %s: %s" % (PINNED_KEY, differing))
    if copy[PINNED_KEY] != str(snapshot_path):
        raise Refusal("config copy %s is %r, expected the snapshot %s" % (PINNED_KEY, copy[PINNED_KEY], snapshot_path))


def make_arm_config(pinned, snapshot_path):
    copy = json.loads(json.dumps(pinned))
    copy[PINNED_KEY] = str(snapshot_path)
    assert_only_root_differs(pinned, copy, snapshot_path)
    return copy


# ---- manifest, plan, per-arm configs ----

def read_manifest(path):
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise Refusal("manifest is not a JSON object")
    missing = [k for k in MANIFEST_KEYS if k not in manifest]
    if missing:
        raise Refusal("manifest lacks: %s" % missing)
    if manifest["track"] not in ("A", "B"):
        raise Refusal("manifest track must be A or B")
    if not isinstance(manifest["arms"], list) or not manifest["arms"] or not all(isinstance(a, str) for a in manifest["arms"]):
        raise Refusal("manifest arms must be a non-empty list of names")
    if not isinstance(manifest["snapshots"], dict):
        raise Refusal("manifest snapshots must map arm names to snapshot ids")
    return manifest


def build_plan(root, manifest):
    arms, snapshots = manifest["arms"], manifest["snapshots"]
    unknown = sorted(set(arms) - set(ARMS))
    if unknown:
        raise Refusal("arms %s have no snapshot route; this wrapper serves only %s" % (unknown, list(ARMS)))
    if set(arms) != set(snapshots):
        raise Refusal("manifest arms and snapshots differ: arms without a snapshot %s, snapshots without an arm %s"
                      % (sorted(set(arms) - set(snapshots)), sorted(set(snapshots) - set(arms))))
    verified = {sid: verify_snapshot(root, sid) for sid in sorted(set(snapshots.values()), key=str)}
    return dict(root=Path(root), snapshots=verified, arms={arm: verified[snapshots[arm]] for arm in arms})


def build_arm_configs(plan, pinned, loader=None):
    """One validated config per arm. The copy is written to a temporary file and read back through the harness's
    own load_config (as harness_farms does for its config); the pinned config itself is never passed to
    load_config, because that would read the live skill's SKILL.md."""
    loader = loader or h.load_config
    folder = Path(tempfile.mkdtemp(prefix="harness_k1_cfg_"))
    result = {}
    try:
        for arm, info in plan["arms"].items():
            copy = make_arm_config(pinned, info["path"])
            target = folder / (arm + ".json")
            target.write_text(json.dumps(copy, indent=2), encoding="utf-8")
            loaded = loader(target)
            assert_only_root_differs(pinned, loaded, info["path"])
            result[arm] = loaded
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    return result


def make_stamps(plan, k1_md5, farms_md5, config_md5):
    return {arm: dict(snapshot_id=info["id"], snapshot_tree_md5=info["tree_md5"], harness_k1_md5=k1_md5,
                      harness_farms_md5=farms_md5, config_md5=config_md5)
            for arm, info in plan["arms"].items()}


# ---- the batch ----

def check_serving(runner, plan, arm, skills):
    """Each invocation must carry this arm's config; arms with the token skill must serve it from this arm's snapshot."""
    if arm not in plan["arms"]:
        raise Refusal("invocation for arm %r, which has no snapshot" % (arm,))
    want = plan["arms"][arm]["path"]
    if _norm(runner.config.get(PINNED_KEY)) != _norm(want):
        raise Refusal("runner config for arm %s does not point at its snapshot %s" % (arm, want))
    served = [Path(p) for p in (skills or {}).values()]
    if arm in TOKEN_ARMS and not any(_norm(p) == _norm(want) for p in served):
        raise Refusal("arm %s does not serve the token skill from its snapshot %s" % (arm, want))
    live = Path(plan["root"]).resolve() / "skills"
    if any(_is_under(p, live) or _is_under(p.resolve(), live) for p in served):
        raise Refusal("arm %s serves a skill from the live skills folder" % arm)


def install_stamping(runner, plan, stamps):
    """Wrap runner.invoke so that every invocation (task, edit, triple, probe) carries the stamp in its metadata."""
    original = runner.invoke

    def invoke(*args, **kw):
        if len(args) < 6 or len(args) > 9:
            raise Refusal("unexpected Runner.invoke call shape")
        arm, skills = args[5], args[1]
        check_serving(runner, plan, arm, skills)
        meta = dict(kw.get("metadata") or {})
        clash = sorted(set(meta) & set(stamps[arm]))
        if clash:
            raise Refusal("metadata keys already in use: %s" % clash)
        meta.update(stamps[arm])
        kw["metadata"] = meta
        return original(*args, **kw)
    runner.invoke = invoke


def run_batch(runner, manifest, plan, arm_configs, stamps, seed):
    """The harness_farms.batch loop with one addition: the runner's config is set to the arm's copy before each
    run, so skill_set (and runlib's trigger-skill read) see that arm's snapshot. Arms run through farms.run_any."""
    install_stamping(runner, plan, stamps)
    output = []
    for task in manifest["tasks"]:
        for round_id, position, arm in r.block_order(manifest["arms"], manifest["rounds"], seed):
            runner.config = json.loads(json.dumps(arm_configs[arm]))
            output.append(farms.run_any(runner, manifest["track"], task, arm, dict(round=round_id, position=position)))
    cells = {}
    for record in output:
        cells.setdefault((record["task_or_fixture_id"], record["arm"]), []).append(record)
    if any(not any(h.valid(record) for record in records) for records in cells.values()):
        raise r.RunError("task-and-arm cell has no valid run left")
    return output


def tree_check(plan):
    return {sid: tree_md5(info["path"]) for sid, info in plan["snapshots"].items()}


def guarded(plan, do_batch, records, sidecar_dir=None, batch_id=None):
    """Recompute every snapshot's tree md5 before and after the batch. A change refuses the batch result;
    records already written are reported, not deleted, and a SNAPSHOT_CHANGED-<batch id>.json sidecar lists them."""
    now = tree_check(plan)
    moved = {sid: (plan["snapshots"][sid]["tree_md5"], d) for sid, d in now.items() if d != plan["snapshots"][sid]["tree_md5"]}
    if moved:
        raise Refusal("snapshot changed before the batch: %s" % moved)
    failure, result = None, None
    try:
        result = do_batch()
    except BaseException as exc:  # re-raised below after the tree check
        failure = exc
    after = tree_check(plan)
    changed = {sid: (plan["snapshots"][sid]["tree_md5"], d) for sid, d in after.items() if d != plan["snapshots"][sid]["tree_md5"]}
    if changed:
        written = [rec.get("run_id") for rec in records()]
        message = ("snapshot tree md5 changed during the batch (snapshot: (before, after)): %s; "
                   "records already written are kept and are NOT valid evidence: %s" % (changed, written))
        if sidecar_dir is not None:
            sidecar = Path(sidecar_dir) / ("SNAPSHOT_CHANGED-%s.json" % batch_id)
            try:
                r.dump(sidecar, dict(batch_id=batch_id, run_ids=written,
                                     snapshots=[dict(snapshot_id=sid, tree_md5_before=b, tree_md5_after=a) for sid, (b, a) in sorted(changed.items())]))
                message += "; sidecar: %s" % sidecar
            except OSError as exc:
                message += "; sidecar NOT written (%s): %s" % (type(exc).__name__, sidecar)
        if failure is not None:
            message += "; the batch had also failed: %s" % failure
        raise Refusal(message)
    if failure is not None:
        raise failure
    return result


def safe_message(exc, credentials_file):
    text = str(exc)
    try:
        return r.redact(text.encode(), credentials_file).decode()
    except Exception:
        return "%s (message not scrubbed: credentials file unreadable)" % type(exc).__name__


def main(argv=None):
    k1_md5 = file_md5(__file__)  # computed at start, from this file's own bytes
    try:
        siblings = check_siblings()
    except Refusal as exc:
        print("HARNESS_K1 REFUSED: " + str(exc), file=sys.stderr, flush=True)
        return 1
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", nargs="?", choices=["batch"])
    p.add_argument("--config", type=Path)
    p.add_argument("--manifest", type=Path)
    p.add_argument("--selftest", action="store_true")
    args = p.parse_args(argv)
    if args.selftest:
        return 0 if selftest() else 1
    if args.command != "batch" or args.config is None or args.manifest is None:
        p.error("batch requires --config and --manifest")
    if argv is None and Path(sys.argv[0]).name.lower() != SCRIPT_NAME:
        print("HARNESS_K1 REFUSED: run this file as %s so launcher.argv0 is recorded correctly" % SCRIPT_NAME, file=sys.stderr)
        return 1
    try:
        root = repo_root()
        pinned, config_md5 = read_pinned_config(args.config)
        manifest = read_manifest(args.manifest)
        plan = build_plan(root, manifest)
        arm_configs = build_arm_configs(plan, pinned)
    except Exception as exc:
        print("HARNESS_K1 REFUSED: " + str(exc), file=sys.stderr, flush=True)
        return 1
    print("harness_k1_md5=%s config_md5=%s repo_root=%s" % (k1_md5, config_md5, root), file=sys.stderr, flush=True)
    for arm, info in plan["arms"].items():
        print("arm %s snapshot %s tree_md5 %s" % (arm, info["id"], info["tree_md5"]), file=sys.stderr, flush=True)
    for key in ("pricing_tools", "rates_path"):
        if key in pinned and _is_under(Path(pinned[key]).resolve(), root / "skills"):
            print("NOTICE: config %s points into the live skills folder; runlib reads it for the cost assertion "
                  "(unchanged by ADR-24, config differs only in %s)" % (key, PINNED_KEY), file=sys.stderr, flush=True)
    first = arm_configs[manifest["arms"][0]]
    runner = None
    try:
        runner = r.Runner(first, log_dir=Path(first["log_root"]))
        stamps = make_stamps(plan, k1_md5, siblings["harness_farms.py"], config_md5)
        output = guarded(plan, lambda: run_batch(runner, manifest, plan, arm_configs, stamps, first["seed"]),
                         lambda: runner.records, sidecar_dir=runner.logs, batch_id=runner.batch_id)
        print(json.dumps(output, sort_keys=True, indent=2), flush=True)
        return 0
    except Exception as exc:
        print("HARNESS FAILED: " + safe_message(exc, first["credentials_file"]), file=sys.stderr, flush=True)
        return 1
    finally:
        if runner:
            runner.checkpoint()


# ---- selftest: writes only inside one tempfile.mkdtemp() folder; launches nothing ----

SHELL_RECIPE = "find . -type f -not -path '*/__pycache__/*' | LC_ALL=C sort | xargs md5sum | md5sum"
KNOWN_AB_TREE = "252ad4fc384056ae839bc616a73fc272"  # a.txt = b'x', sub/b.txt = b'y'; value of SHELL_RECIPE on Linux


def _find_bash():
    candidates = []
    if os.name == "nt":
        for var in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
            if os.environ.get(var):
                candidates.append(Path(os.environ[var]) / "Git" / "bin" / "bash.exe")
    found = shutil.which("bash")
    if found and os.name != "nt":
        candidates.append(Path(found))
    for c in candidates:
        if c.is_file():
            return str(c)
    return found


def shell_tree_md5(folder):
    bash = _find_bash()
    if not bash:
        raise RuntimeError("no bash found to run the shell recipe")
    # The recipe's listing stage (everything before the final md5sum) runs in bash; the outer md5 is taken here.
    # Git Bash's md5sum on Windows runs in binary mode and prints "<md5> *./path" where GNU md5sum on Linux prints
    # "<md5>  ./path" (run 20261028T142913Z: recipe 2420e2c9 against routine and f2 constant 252ad4fc). The binary
    # marker is normalised to the Linux text form, the form ADR-24's values (eda5e150, 0f7bd41b) were computed in;
    # any other difference still fails the comparison.
    listing_cmd = SHELL_RECIPE.rsplit("|", 1)[0].strip()
    script = "set -o pipefail; PATH=/usr/bin:/bin:$PATH; " + listing_cmd  # keep the Unix find and sort ahead of Windows ones
    out = subprocess.run([bash, "-c", script], cwd=str(folder), env=dict(os.environ, LC_ALL="C"),
                         stdin=subprocess.DEVNULL, capture_output=True, timeout=60, check=True)
    text = out.stdout.decode("utf-8")
    if os.name == "nt":
        text = text.replace("\r\n", "\n")
    text = re.sub(r"(?m)^([0-9a-f]{32}) \*", r"\1  ", text)
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _write(folder, files):
    for rel, data in files.items():
        target = Path(folder) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def make_snapshot(root, files, name=None):
    """Write files into candidates/_stage/token-aware, then rename _stage to the tree md5 prefix (or to name)."""
    stage = Path(root) / "candidates" / "_stage"
    _write(stage / "token-aware", files)
    digest = tree_md5(stage / "token-aware")
    target = Path(root) / "candidates" / (name or digest[:8])
    stage.rename(target)
    return digest, target / "token-aware"


def make_fake_root(base):
    root = Path(base) / "repo"
    (root / "notes" / "project").mkdir(parents=True)
    (root / "notes" / "token-aware" / "eval" / "harness").mkdir(parents=True)
    (root / "skills" / "token-aware").mkdir(parents=True)
    (root / "skills" / "token-aware" / "SKILL.md").write_bytes(b"---\nname: token-aware\n---\nlive\n")
    (root / "candidates").mkdir()
    return root.resolve()


def _refuses(fn, fragment=""):
    try:
        fn()
    except Refusal as exc:
        return fragment in str(exc)
    return False


class _FakeRunner:
    def __init__(self, config, log):
        self.config, self.log, self.records = config, log, []

    def invoke(self, prompt, skills, files, track, item, arm, work_source=None, check=None, metadata=None, snapshot=None):
        rec = dict(run_id="fake-%04d" % (len(self.records) + 1), task_or_fixture_id=item, arm=arm, flags=[],
                   prompt=prompt, root_at_call=self.config[PINNED_KEY], skills=dict(skills), track=track)
        rec.update(metadata or {})
        self.records.append(rec)
        self.log.append(rec)
        return rec


def selftest():
    results = []
    launches = []
    base = Path(tempfile.mkdtemp(prefix="harness_k1_selftest_"))
    k1_md5 = file_md5(__file__)
    farms_md5 = file_md5(HERE / "harness_farms.py")
    config_md5 = "0123456789abcdef0123456789abcdef"

    def tripwire(*a, **k):
        launches.append("launch attempted")
        raise AssertionError("selftest must not launch anything")

    saved = dict(child=r.child, version=r.version, Runner=r.Runner, skill_set=h.skill_set, run_task=h.run_task, track_a=h.track_a)
    r.child = r.version = r.Runner = tripwire
    try:
        def case(name, fn):
            try:
                outcome = fn()
                results.append((name, "SKIP" if outcome == "SKIP" else "OK"))
            except Exception as exc:  # any failure of a case, including a wrong exception type
                results.append((name, "FAIL"))
                print("  detail %s: %s: %s" % (name, type(exc).__name__, exc), file=sys.stderr)

        def need(condition, what):
            if not condition:
                raise AssertionError(what)

        root = make_fake_root(base)
        files_a = {"SKILL.md": b"---\nname: token-aware\n---\nbody a\n", "references/x.md": b"x\n", "__pycache__/m.pyc": b"junk"}
        files_b = {"SKILL.md": b"---\nname: token-aware\n---\nbody b\n", "references/x.md": b"x\n"}
        digest_a, path_a = make_snapshot(root, files_a)
        digest_b, path_b = make_snapshot(root, files_b)
        id_a, id_b = digest_a[:8], digest_b[:8]
        pinned = json.loads((HERE / "config.s2h.json").read_text(encoding="utf-8")) if (HERE / "config.s2h.json").is_file() else None
        if pinned is None:
            pinned = {"seed": 1, "tool_set": ["Read", "Bash"], "dry_run": {"task": "T01"}, PINNED_KEY: str(root / "skills" / "token-aware")}

        def a_live_root():
            need(_refuses(lambda: refuse_live(root / "skills" / "token-aware", root), "live skills"), "plain skills path accepted")
            need(_refuses(lambda: refuse_live(root / "candidates" / ".." / "skills" / "token-aware", root), "live skills"), "dotted path accepted")
            refuse_live(path_a, root)  # a candidate is not refused
        case("a_root_under_skills_refused", a_live_root)

        def a2_link():
            link = root / "candidates" / "deadbeef"
            try:
                os.symlink(root / "skills", link, target_is_directory=True)
            except (OSError, NotImplementedError, AttributeError):
                return "SKIP"
            need(_refuses(lambda: verify_snapshot(root, "deadbeef"), "live skills"), "link into skills accepted")
            link.unlink()
        case("a2_link_into_skills_refused", a2_link)

        def b_name_mismatch():
            _, wrong = make_snapshot(root, {"SKILL.md": b"---\nname: token-aware\n---\nc\n"}, name="0badf00d")
            need(_refuses(lambda: verify_snapshot(root, "0badf00d"), "differs from the first 8"), "wrong-named snapshot accepted")
            for bad in ("ABCDEF12", "abc", "zzzzzzzz", None, "../skills", id_a + "\n"):
                need(_refuses(lambda b=bad: verify_snapshot(root, b), "8 lower-case hex"), "bad id accepted: %r" % (bad,))
        case("b_name_differs_from_tree_md5_refused", b_name_mismatch)

        def c_config_copy():
            good = make_arm_config(pinned, path_a)
            tampered = []
            for key in sorted(k for k in pinned if k != PINNED_KEY):
                value = json.loads(json.dumps(pinned[key]))
                if isinstance(value, bool):
                    value = not value
                elif isinstance(value, (int, float)):
                    value = value + 1
                elif isinstance(value, str):
                    value = value + "x"
                elif isinstance(value, list):
                    value = value + ["extra"]
                elif isinstance(value, dict):
                    value = dict(value, extra=1)
                else:
                    value = "changed"
                tampered.append(dict(good, **{key: value}))
            nested = json.loads(json.dumps(good))
            nested["dry_run"]["task"] = "T99" if "dry_run" in nested else None
            tampered.append(nested)
            tampered.append({k: v for k, v in good.items() if k != "seed"})
            tampered.append(dict(good, added_key=1))
            tampered.append(dict(good, seed=float(good["seed"])) if isinstance(good["seed"], int) else dict(good, seed=str(good["seed"])))
            tampered.append(dict(good, **{PINNED_KEY: str(root / "skills" / "token-aware")}))
            for t in tampered:
                need(_refuses(lambda t=t: assert_only_root_differs(pinned, t, path_a)), "tampered copy accepted: %s" % sorted(set(t) ^ set(good)))
            need(len(tampered) >= len(pinned) + 3, "too few tampering variants")
        case("c_config_copy_other_key_refused", c_config_copy)

        def d_positive():
            info = verify_snapshot(root, id_a)
            need(info["tree_md5"] == digest_a and info["path"] == path_a, "snapshot description wrong")
            copy = make_arm_config(pinned, info["path"])
            assert_only_root_differs(pinned, copy, info["path"])
            need(copy[PINNED_KEY] == str(path_a) and pinned[PINNED_KEY] != copy[PINNED_KEY], "root not replaced")
            need(canon({k: v for k, v in copy.items() if k != PINNED_KEY}) == canon({k: v for k, v in pinned.items() if k != PINNED_KEY}), "other keys differ")
            need(digest_a == tree_md5(path_a), "pycache file changed the tree md5")
            manifest = dict(track="B", tasks=["T01"], arms=["K0", "K1"], rounds=1, snapshots=dict(K0=id_a, K1=id_b))
            plan = build_plan(root, manifest)
            configs = build_arm_configs(plan, pinned, loader=lambda p: json.loads(Path(p).read_text(encoding="utf-8")))
            need(configs["K0"][PINNED_KEY] == str(path_a) and configs["K1"][PINNED_KEY] == str(path_b), "arm configs wrong")
        case("d_correct_snapshot_and_config_pass", d_positive)

        def e_farms():
            logged = []
            eval_root = base / "evalroot"
            (eval_root / "tasks" / "T01").mkdir(parents=True)
            (eval_root / "tasks" / "T01" / "task.md").write_text("Do the thing.\n", encoding="utf-8")
            seen = []
            h.skill_set = lambda c, arm, fixture=None: seen.append((arm, c[PINNED_KEY])) or ({} if arm in ("N", "AN") else {"token-aware": Path(c[PINNED_KEY])})
            h.run_task = lambda runner, task, arm, meta=None: runner.invoke("plain " + task, h.skill_set(runner.config, arm), {}, "B", task, arm, metadata=meta)

            def fake_track_a(runner, fixture, arm, dry_run=False, metadata=None):
                first = runner.invoke("edit", h.skill_set(runner.config, arm), {}, "A", fixture, arm, metadata=metadata)
                runner.invoke("triple", h.skill_set(runner.config, arm), {}, "A", fixture, arm, metadata=dict(triple=0))
                return first
            h.track_a = fake_track_a
            snaps = dict(K0=id_a, K1=id_b, K0f=id_a, K1f=id_b)
            manifest = dict(track="B", tasks=["T01"], arms=list(snaps), rounds=2, snapshots=snaps)
            plan = build_plan(root, manifest)
            pin = dict(pinned, eval_root=str(eval_root))
            configs = build_arm_configs(plan, pin, loader=lambda p: json.loads(Path(p).read_text(encoding="utf-8")))
            runner = _FakeRunner(json.loads(json.dumps(configs["K0"])), logged)
            out = run_batch(runner, manifest, plan, configs, make_stamps(plan, k1_md5, farms_md5, config_md5), 20261019)
            need(len(out) == 8, "expected 8 runs, got %d" % len(out))
            need([x["arm"] for x in out] == [a for _, _, a in r.block_order(list(snaps), 2, 20261019)], "block order differs from the harness")
            for rec in out:
                info = plan["arms"][rec["arm"]]
                need(rec["root_at_call"] == str(info["path"]), "%s ran on the wrong root" % rec["arm"])
                need(rec["snapshot_id"] == info["id"] and rec["snapshot_tree_md5"] == info["tree_md5"] and len(rec["snapshot_tree_md5"]) == 32, "stamp wrong")
                need(rec["harness_k1_md5"] == k1_md5 and len(k1_md5) == 32, "own md5 not stamped")
                need(rec["harness_farms_md5"] == farms_md5 and re.fullmatch("[0-9a-f]{32}", farms_md5), "farms md5 not stamped")
                need(("round" in rec and "position" in rec), "harness metadata lost")
                is_f = rec["arm"].endswith("f")
                need(rec["prompt"].endswith("\n\nUse the token-aware skill.\n") == is_f, "f line misplaced for %s" % rec["arm"])
            need(all(arm in ("K0", "K1") for arm, _ in seen) and {a for a, _ in seen} == {"K0", "K1"}, "f arms must install K0 and K1 skill sets: %s" % seen)
            need(not [x for x in out if x["arm"] in ("K0f", "K1f") and not x["prompt"].startswith("Do the thing.")], "f prompt lost the task text")
            # arms N and AN: mapped to a snapshot, stamped, run on that snapshot's config, no token skill served
            logged.clear()
            snaps_n = dict(N=id_b, K0=id_a)
            manifest_n = dict(track="B", tasks=["T01"], arms=list(snaps_n), rounds=1, snapshots=snaps_n)
            plan_n = build_plan(root, manifest_n)
            configs_n = build_arm_configs(plan_n, pin, loader=lambda p: json.loads(Path(p).read_text(encoding="utf-8")))
            runner_n = _FakeRunner(json.loads(json.dumps(configs_n["K0"])), logged)
            out_n = run_batch(runner_n, manifest_n, plan_n, configs_n, make_stamps(plan_n, k1_md5, farms_md5, config_md5), 3)
            by_arm = {x["arm"]: x for x in out_n}
            need(by_arm["N"]["root_at_call"] == str(path_b) and by_arm["N"]["snapshot_id"] == id_b and by_arm["N"]["skills"] == {}, "N arm not served as expected")
            need(by_arm["K0"]["root_at_call"] == str(path_a), "K0 beside N on the wrong root")
            logged.clear()
            manifest_an = dict(track="A", tasks=["F2"], arms=["AN"], rounds=1, snapshots=dict(AN=id_b))
            plan_an = build_plan(root, manifest_an)
            configs_an = build_arm_configs(plan_an, pin, loader=lambda p: json.loads(Path(p).read_text(encoding="utf-8")))
            runner_an = _FakeRunner(json.loads(json.dumps(configs_an["AN"])), logged)
            run_batch(runner_an, manifest_an, plan_an, configs_an, make_stamps(plan_an, k1_md5, farms_md5, config_md5), 3)
            need(len(logged) == 2 and all(x["snapshot_id"] == id_b and x["root_at_call"] == str(path_b) for x in logged), "AN not stamped on both invocations")
            # track A: both the edit record and the later triple invocation are stamped
            logged.clear()
            manifest_a = dict(track="A", tasks=["F2"], arms=["AS"], rounds=1, snapshots=dict(AS=id_b))
            plan_a = build_plan(root, manifest_a)
            configs_a = build_arm_configs(plan_a, pinned, loader=lambda p: json.loads(Path(p).read_text(encoding="utf-8")))
            runner_a = _FakeRunner(json.loads(json.dumps(configs_a["AS"])), logged)
            run_batch(runner_a, manifest_a, plan_a, configs_a, make_stamps(plan_a, k1_md5, farms_md5, config_md5), 1)
            need(len(logged) == 2 and all(x.get("snapshot_id") == id_b for x in logged) and logged[1]["triple"] == 0, "track A invocations not all stamped")
            # f arm on track A is refused by farms.run_any
            bad = dict(track="A", tasks=["F2"], arms=["K0f"], rounds=1, snapshots=dict(K0f=id_a))
            plan_bad = build_plan(root, bad)
            cfg_bad = build_arm_configs(plan_bad, pinned, loader=lambda p: json.loads(Path(p).read_text(encoding="utf-8")))
            rb = _FakeRunner(json.loads(json.dumps(cfg_bad["K0f"])), [])
            try:
                run_batch(rb, bad, plan_bad, cfg_bad, make_stamps(plan_bad, k1_md5, farms_md5, config_md5), 1)
                raise AssertionError("f arm on track A accepted")
            except r.RunError:
                pass
        case("e_farms_delegation_monkeypatched", e_farms)
        h.skill_set, h.run_task, h.track_a = saved["skill_set"], saved["run_task"], saved["track_a"]

        def g_serving_guard():
            plan = build_plan(root, dict(track="B", tasks=["T"], arms=["K0", "K1"], rounds=1, snapshots=dict(K0=id_a, K1=id_b)))
            cfgs = build_arm_configs(plan, pinned, loader=lambda p: json.loads(Path(p).read_text(encoding="utf-8")))
            runner = _FakeRunner(json.loads(json.dumps(cfgs["K0"])), [])
            check_serving(runner, plan, "K0", {"token-aware": path_a})
            need(_refuses(lambda: check_serving(runner, plan, "K1", {"token-aware": path_b}), "does not point"), "config of another arm accepted")
            need(_refuses(lambda: check_serving(runner, plan, "K0", {"token-aware": path_b}), "does not serve"), "skill from another snapshot accepted")
            need(_refuses(lambda: check_serving(runner, plan, "K0", {"token-aware": path_a, "x": root / "skills" / "token-aware"}), "live skills"), "live skill accepted")
            need(_refuses(lambda: check_serving(runner, plan, "N", {}), "no snapshot"), "arm outside the plan accepted")
            plan_n = build_plan(root, dict(track="B", tasks=["T"], arms=["N", "AN"], rounds=1, snapshots=dict(N=id_a, AN=id_a)))
            cfg_n = build_arm_configs(plan_n, pinned, loader=lambda p: json.loads(Path(p).read_text(encoding="utf-8")))
            runner_n = _FakeRunner(json.loads(json.dumps(cfg_n["N"])), [])
            check_serving(runner_n, plan_n, "N", {})
            need(_refuses(lambda: check_serving(runner_n, plan_n, "N", {"x": root / "skills" / "token-aware"}), "live skills"), "N served live skill")
        case("g_wrong_serving_refused", g_serving_guard)

        def f_shell():
            # Names are distinct under case folding, so the tree is the same on NTFS (case-insensitive) as on
            # Linux; uppercase-first byte order is still exercised ("B.txt", "Q.txt", "Z/y" sort before "_x" and "a...").
            # f2 (a precomputed constant) is the authority on Windows; this case compares against the live shell recipe
            # and reports SKIP with the reason when no bash can be started (for example inside a sandbox).
            folder = base / "ab"
            _write(folder, {"a.txt": b"x", "sub/b.txt": b"y"})
            try:
                shell = shell_tree_md5(folder)
            except (OSError, RuntimeError) as exc:  # no bash found, or bash could not be launched; a recipe that ran and failed is a FAIL
                print("  detail f_tree_md5_equals_shell_recipe: SKIP, shell recipe not runnable here: %s" % exc, file=sys.stderr)
                return "SKIP"
            mine = tree_md5(folder)
            need(mine == shell, "routine %s differs from the shell recipe %s" % (mine, shell))
            _write(folder, {"__pycache__/c.pyc": b"z", "sub/__pycache__/d.pyc": b"w", "sub/Q_r.txt": b"q"})
            names = ("B.txt", "a-b", "a/b", "a.b/c", "Z/y", "zz", "_x", "Q.txt")
            _write(folder, {n: n.encode() for n in names})
            folded = [str(x.relative_to(folder)).lower() for x in folder.rglob("*")]
            need(len(folded) == len(set(folded)), "test tree has names that collide under case folding")
            need(tree_md5(folder) == shell_tree_md5(folder), "routine differs from the shell recipe with pycache, case and punctuation in names")
        case("f_tree_md5_equals_shell_recipe", f_shell)

        def f2_constant():
            folder = base / "ab2"
            _write(folder, {"a.txt": b"x", "sub/b.txt": b"y"})
            need(tree_md5(folder) == KNOWN_AB_TREE, "known value not reproduced")
            moved = base / "ab3"
            shutil.copytree(folder, moved)
            need(tree_md5(moved) == KNOWN_AB_TREE, "tree md5 depends on location")
        case("f2_tree_md5_known_value", f2_constant)

        def h_repo_root():
            fake_script = root / "notes" / "token-aware" / "eval" / "harness" / SCRIPT_NAME
            need(repo_root(fake_script) == root, "parents[4] did not give the root")
            elsewhere = base / "x" / "y" / "z" / "w" / "v" / SCRIPT_NAME
            elsewhere.parent.mkdir(parents=True)
            need(_refuses(lambda: repo_root(elsewhere), "notes/project"), "root without notes/project accepted")
            need(_refuses(lambda: repo_root(Path("/")), ""), "shallow path accepted")
        case("h_repo_root_checked", h_repo_root)

        def i_manifest():
            ok = dict(track="B", tasks=["T"], arms=["K0", "K1"], rounds=1, snapshots=dict(K0=id_a, K1=id_b))
            build_plan(root, ok)
            build_plan(root, dict(ok, arms=["K0", "N", "AN"], snapshots=dict(K0=id_a, N=id_b, AN=id_a)))
            need(_refuses(lambda: build_plan(root, dict(ok, arms=["K0", "X"], snapshots=dict(K0=id_a, X=id_b))), "no snapshot route"), "unknown arm accepted")
            need(_refuses(lambda: build_plan(root, dict(ok, arms=["K0", "N"], snapshots=dict(K0=id_a))), "without a snapshot"), "N without snapshot accepted")
            need(_refuses(lambda: build_plan(root, dict(ok, snapshots=dict(K0=id_a))), "without a snapshot"), "missing snapshot accepted")
            need(_refuses(lambda: build_plan(root, dict(ok, snapshots=dict(K0=id_a, K1=id_b, AS=id_a))), "without an arm"), "extra snapshot accepted")
            need(_refuses(lambda: build_plan(root, dict(ok, snapshots=dict(K0=id_a, K1="00000000")), ), "missing"), "absent snapshot folder accepted")
            for broken in (dict(ok, track="C"), {k: v for k, v in ok.items() if k != "snapshots"}, dict(ok, arms=[])):
                target = base / "m.json"
                target.write_text(json.dumps(broken), encoding="utf-8")
                need(_refuses(lambda: read_manifest(target)), "broken manifest accepted")
        case("i_manifest_rules", i_manifest)

        def j_config_pin():
            f = base / "c.json"
            f.write_text(json.dumps(pinned), encoding="utf-8")
            need(_refuses(lambda: read_pinned_config(f), "pinned"), "unpinned config accepted")
            global CONFIG_MD5_PREFIX
            real_prefix, CONFIG_MD5_PREFIX = CONFIG_MD5_PREFIX, file_md5(f)[:8]  # test-only monkeypatch of the pin
            try:
                cfg, digest = read_pinned_config(f)
            finally:
                CONFIG_MD5_PREFIX = real_prefix
            need(cfg == pinned and len(digest) == 32, "patched pin did not pass the config")
            need(_refuses(lambda: read_pinned_config(f), "pinned"), "pin not restored")
            need("allow-config-md5" not in subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "--help"], capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=60).stdout, "bypass flag still offered")
            if (HERE / "config.s2h.json").is_file() and file_md5(HERE / "config.s2h.json").startswith(CONFIG_MD5_PREFIX):
                read_pinned_config(HERE / "config.s2h.json")
        case("j_config_md5_pin", j_config_pin)

        def k_tree_change():
            _, mutable = make_snapshot(root, {"SKILL.md": b"---\nname: token-aware\n---\nm1\n"})
            plan = build_plan(root, dict(track="B", tasks=["T"], arms=["K0"], rounds=1, snapshots=dict(K0=tree_md5(mutable)[:8])))
            need(guarded(plan, lambda: "done", lambda: []) == "done", "unchanged snapshot refused")

            def mutate():
                (mutable / "SKILL.md").write_bytes(b"changed\n")
                return "done"
            try:
                guarded(plan, mutate, lambda: [dict(run_id="rec-1"), dict(run_id="rec-2")])
                raise AssertionError("change during the batch accepted")
            except Refusal as exc:
                need("rec-1" in str(exc) and "rec-2" in str(exc) and "changed during the batch" in str(exc), "message lacks the records: %s" % exc)
            need(_refuses(lambda: guarded(plan, lambda: "x", lambda: []), "before the batch"), "pre-batch change accepted")
            # sidecar: written on a mismatch, with run_ids, snapshot id and both md5 values
            _, mutable2 = make_snapshot(root, {"SKILL.md": b"---\nname: token-aware\n---\nm2\n"})
            sid2 = tree_md5(mutable2)[:8]
            before2 = tree_md5(mutable2)
            plan2 = build_plan(root, dict(track="B", tasks=["T"], arms=["K0"], rounds=1, snapshots=dict(K0=sid2)))
            logs = base / "logs"
            logs.mkdir()

            def mutate2():
                (mutable2 / "SKILL.md").write_bytes(b"changed again\n")
            try:
                guarded(plan2, mutate2, lambda: [dict(run_id="rec-7")], sidecar_dir=logs, batch_id="B1")
                raise AssertionError("change during the batch accepted")
            except Refusal as exc:
                side = logs / "SNAPSHOT_CHANGED-B1.json"
                need(str(side) in str(exc) and side.is_file(), "sidecar path not in the refusal or file missing")
                data = json.loads(side.read_text(encoding="utf-8"))
                need(data["run_ids"] == ["rec-7"] and data["snapshots"] == [dict(snapshot_id=sid2, tree_md5_before=before2, tree_md5_after=tree_md5(mutable2))], "sidecar content wrong: %s" % data)
                need(sorted(p.name for p in logs.iterdir()) == ["SNAPSHOT_CHANGED-B1.json"], "unexpected files in the records folder")
        case("k_tree_change_during_batch_refused", k_tree_change)

        def p_real_load_config():
            snap_dir = verify_snapshot(root, id_a)["path"]
            fake_bash = base / "bash.exe"
            fake_bash.write_bytes(b"")
            pin = dict(pinned, eval_root=str(r.EVAL_ROOT), git_bash_path=str(fake_bash))  # test copy only
            plan = build_plan(root, dict(track="B", tasks=["T"], arms=["K0"], rounds=1, snapshots=dict(K0=id_a)))
            try:
                configs = build_arm_configs(plan, pin)  # loader = the real h.load_config, on a temp copy of the arm config
            except r.RunError as exc:
                if "only the pinned local native claude.exe" in str(exc):
                    print("  detail p_real_load_config: SKIP, load_config insists on the Windows claude.exe path: %s" % exc, file=sys.stderr)
                    return "SKIP"
                raise
            need(configs["K0"][PINNED_KEY] == str(snap_dir), "real load_config result does not point at the snapshot")
            need(not any(p == _norm(root / "skills" / "token-aware") for p in [_norm(configs["K0"][PINNED_KEY])]), "live skill root in the loaded config")
        case("p_real_load_config_on_temp_copy", p_real_load_config)

        def o_siblings():
            copy = base / "siblings"
            copy.mkdir()
            for name in PINNED_SIBLINGS:
                shutil.copyfile(HERE / name, copy / name)
            need(set(check_siblings(copy)) == set(PINNED_SIBLINGS), "pinned siblings refused")
            (copy / "runlib.py").write_bytes((copy / "runlib.py").read_bytes() + b"\n# changed\n")
            need(_refuses(lambda: check_siblings(copy), "runlib.py"), "wrong sibling md5 accepted")
            (copy / "runlib.py").write_bytes((HERE / "runlib.py").read_bytes())
            (copy / "harness_farms.py").unlink()
            need(_refuses(lambda: check_siblings(copy), "missing"), "missing sibling accepted")
        case("o_wrong_sibling_md5_refused", o_siblings)

        def l_clash():
            plan = build_plan(root, dict(track="B", tasks=["T"], arms=["K0"], rounds=1, snapshots=dict(K0=id_a)))
            cfgs = build_arm_configs(plan, pinned, loader=lambda p: json.loads(Path(p).read_text(encoding="utf-8")))
            runner = _FakeRunner(json.loads(json.dumps(cfgs["K0"])), [])
            install_stamping(runner, plan, make_stamps(plan, k1_md5, farms_md5, config_md5))
            need(_refuses(lambda: runner.invoke("p", {"token-aware": path_a}, {}, "B", "T", "K0", metadata=dict(snapshot_id="x")), "already in use"), "metadata clash accepted")
        case("l_stamp_clash_refused", l_clash)
    finally:
        r.child, r.version, r.Runner = saved["child"], saved["version"], saved["Runner"]
        h.skill_set, h.run_task, h.track_a = saved["skill_set"], saved["run_task"], saved["track_a"]
        shutil.rmtree(base, ignore_errors=True)
    results.append(("m_nothing_launched", "OK" if not launches else "FAIL"))
    results.append(("n_harness_modules_unpatched", "OK" if (h.skill_set is saved["skill_set"] and h.__file__.endswith("harness.py") and r.Runner is saved["Runner"]) else "FAIL"))
    for name, status in results:
        print("SELFTEST %s %s" % (name, status))
    return all(status in ("OK", "SKIP") for _, status in results)


if __name__ == "__main__":
    sys.exit(main())

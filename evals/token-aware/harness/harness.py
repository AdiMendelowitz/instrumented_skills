"""Controlled evaluation CLI. Live entry points require an explicit configuration."""
import argparse
import json
import math
import random
import statistics
import sys
from pathlib import Path

import runlib as r

TRIPLE_PROMPT = "Reply with the single word OK."
EDIT_PROMPT = "Shorten CLAUDE.md and the files it imports so they cost fewer tokens, without removing any instruction."
HERE = Path(__file__).resolve().parent


def load_config(path):
    c = json.loads(Path(path).read_text(encoding="utf-8"))
    for key in ("claude_binary","claude_version","temp_root","credentials_file","model_id","seed","log_root","pricing_tools","permission_flags","cost_assertion_cap","trigger_skill","eval_root","shell_tool","tool_set","token_skill_root"):
        if key not in c:
            raise r.RunError("missing config setting: "+key)
    if Path(c["claude_binary"]).resolve() != Path(r"C:\Users\REDACTED_USER\venvs\token-aware-eval\claude-code\node_modules\@anthropic-ai\claude-code\bin\claude.exe").resolve():
        raise r.RunError("only the pinned local native claude.exe may be called")
    if Path(c["eval_root"]).resolve() != r.EVAL_ROOT.resolve():
        raise r.RunError("eval_root differs from this harness")
    token_name = r.skill_frontmatter_name(Path(c["token_skill_root"])/"SKILL.md")
    if token_name != c["trigger_skill"]:
        raise r.RunError("token skill frontmatter name differs from config trigger_skill")
    if c["model_id"] != "claude-sonnet-5-5":
        raise r.RunError("gating model must be claude-sonnet-5-5")
    if c["shell_tool"] not in ("Bash","PowerShell") or c["shell_tool"] not in c["tool_set"]:
        raise r.RunError("invalid configured shell tool")
    tools_index = c["permission_flags"].index("--tools")+1
    if c["permission_flags"][tools_index].split(",") != c["tool_set"]:
        raise r.RunError("--tools differs from recorded tool_set")
    if c["shell_tool"] == "Bash" and not Path(c.get("git_bash_path","")).is_file():
        raise r.RunError("configured Git Bash executable is missing")
    return c


def skill_set(c, arm, fixture=None):
    if arm not in ("N","K0","K1","AN","AS","ASn"):
        raise r.RunError("unknown arm")
    if arm.startswith("A"):
        if fixture is None:
            raise r.RunError("track A requires a fixture")
        skills = r.skills_from(Path(fixture)/"skills")
    else:
        skills = r.skills_from(Path(c["eval_root"])/"fixtures"/"G"/"skills")
        if len(skills) != 15:
            raise r.RunError("set G does not have exactly 15 named skills")
    if arm in ("K0","K1","AS","ASn"):
        path = Path(c["token_skill_root"])
        if not (path/"SKILL.md").is_file():
            raise r.RunError("missing token skill")
        name = r.skill_frontmatter_name(path/"SKILL.md")
        if name in skills:
            raise r.RunError("duplicate token skill name")
        skills[name] = path
    return skills


def run_task(runner, task, arm, metadata=None):
    root = Path(runner.config["eval_root"])/"tasks"/task
    r.contained(root,Path(runner.config["eval_root"])/"tasks")
    prompt = (root/"task.md").read_text(encoding="utf-8")
    return runner.invoke(prompt,skill_set(runner.config,arm),{},"B",task,arm,
                         work_source=root/"start",check=root/"check.py",metadata=metadata)


def run_edit(runner, fixture, arm, metadata=None):
    path = Path(runner.config["eval_root"])/"fixtures"/fixture
    r.contained(path,Path(runner.config["eval_root"])/"fixtures")
    edited = {}
    def snapshot(work, cfg):
        edited.update(r.fixture_files(work))
    before = r.fixture_files(path)
    rec = runner.invoke(EDIT_PROMPT,skill_set(runner.config,arm,path),before,
                        "A",fixture,arm,work_source=path,metadata=metadata,snapshot=snapshot)
    rec["edit_evidence"] = edit_evidence(before,edited)
    if not any(v["changed"] for v in rec["edit_evidence"]["files"].values()):
        rec["flags"].append("edit_no_change")
    r.dump(runner.logs/(rec["run_id"]+".record.json"),rec)
    return rec, edited


def edit_evidence(before, after):
    keys = sorted(set(before)|set(after))
    files = {name:dict(bytes_before=len(before[name]) if name in before else 0,
                       bytes_after=len(after[name]) if name in after else 0,
                       changed=before.get(name) != after.get(name)) for name in keys}
    return dict(files=files,total_bytes_before=sum(map(len,before.values())),
                total_bytes_after=sum(map(len,after.values())))


def triples(runner, files, skills, item, arm, count=5, metadata=None):
    if not hasattr(runner,"triple_rng"):
        runner.triple_rng = random.Random(runner.config["seed"])
    rng = runner.triple_rng
    result = []
    for index in range(count):
        order = ["BASE","ONECHAR","FILE"]
        rng.shuffle(order)
        values = {}
        ids = {}
        for position, label in enumerate(order):
            instruction = {} if label == "BASE" else ({"CLAUDE.md":b"x\n"} if label == "ONECHAR" else files)
            meta = dict(metadata or {}, triple=index, triple_order=order, triple_kind=label, position=position)
            rec = runner.invoke(TRIPLE_PROMPT,skills,instruction,"A",item,arm,metadata=meta)
            values[label], ids[label] = r.tokens(rec), rec["run_id"]
        values.update(WRAP=values["ONECHAR"]-values["BASE"]-1,
                      content=values["FILE"]-values["ONECHAR"]+1,
                      order=order,run_ids=ids)
        result.append(values)
    return result


def probes(runner, fixture, arm, files, skills, pass_number=1):
    root = Path(runner.config["eval_root"])/"probes"/fixture
    specs = json.loads((root/"probes.json").read_text(encoding="utf-8"))
    results = []
    for spec in specs:
        prompt_path = r.contained(root/spec["prompt_file"],root)
        grader = r.contained(root/spec["grader"],root)
        source = prompt_path.parent/"start"
        for repeat in range(3):
            rec = runner.invoke(prompt_path.read_text(encoding="utf-8"),skills,files,"A",fixture,arm,
                                work_source=source if source.is_dir() else None,check=grader,
                                metadata=dict(probe_id=spec["id"],repeat=repeat,probe_pass=pass_number))
            results.append(dict(probe=spec["id"],repeat=repeat,pass_number=pass_number,
                                passed=rec["check_exit_code"] == 0, reason=rec["check_reason"],run_id=rec["run_id"],
                                void=not valid(rec)))
    if not results:
        raise r.RunError("empty probe set")
    return results, probe_score(results)


def probe_score(results):
    """Share of passed probe runs among the runs that count (A48: a voided run is neither pass nor fail)."""
    scored = [p for p in results if not p["void"]]
    return sum(p["passed"] for p in scored)/len(scored) if scored else None


def track_a(runner, fixture, arm, dry_run=False, metadata=None):
    start_index = len(runner.records)
    rec, files = run_edit(runner,fixture,arm,metadata)
    fixture_path = Path(runner.config["eval_root"])/"fixtures"/fixture
    skills = skill_set(runner.config,arm,fixture_path)
    values = triples(runner,files,skills,fixture,arm)
    first, first_score = probes(runner,fixture,arm,files,skills)
    second, second_score, fallback = [],None,False
    if not dry_run:
        baseline = runner.config["probe_thresholds"][fixture]
        if len(baseline) != 5:
            raise r.RunError("threshold requires exactly five unedited scores")
        threshold = min(baseline)
        if first_score is None:
            raise r.RunError("every first-pass probe run is void; no probe score")
        if first_score < threshold:
            second, second_score = probes(runner,fixture,arm,files,skills,2)
            fallback = second_score < threshold
    rec.update(triples=values,probe_results=first+second,first_pass_score=first_score,
               second_pass_score=second_score,scored_at_unedited_size=fallback,
               dry_run=dry_run,content_mean=statistics.mean(t["content"] for t in values),
               content_range=[min(t["content"] for t in values),max(t["content"] for t in values)])
    if any("cost_assertion" in invocation["flags"] for invocation in runner.records[start_index:]):
        if "cost_assertion" not in rec["flags"]:
            rec["flags"].append("cost_assertion")
        rec["excluded_from_all_endpoints"] = True
    path = runner.logs/(rec["run_id"]+".record.json")
    serial = json.dumps(rec,sort_keys=True).encode()
    if r.redact(serial,runner.config["credentials_file"]) != serial:
        raise r.RunError("credential found in aggregate record")
    r.dump(path,rec)
    r.credential_check([path],runner.config["credentials_file"])
    return rec


def dose_stats(triples):
    if len(triples) != 20:
        raise r.RunError("dose check requires exactly 20 triples")
    x, y = [t["dose"] for t in triples], [t["content"] for t in triples]
    xm, ym = statistics.mean(x), statistics.mean(y)
    sxx = sum((v-xm)**2 for v in x)
    b = sum((xx-xm)*(yy-ym) for xx,yy in zip(x,y))/sxx
    a = ym-b*xm
    residual_sd = math.sqrt(sum((yy-a-b*xx)**2 for xx,yy in zip(x,y))/(len(x)-2))
    doses = []
    for k in range(1,5):
        group = [t for t in triples if t["dose"] == k]
        contents, wraps = [t["content"] for t in group], [t["WRAP"] for t in group]
        doses.append(dict(dose=k,content_mean=statistics.mean(contents),content_sd=statistics.stdev(contents),
                          wrap_mean=statistics.mean(wraps),wrap_sd=statistics.stdev(wraps),
                          fitted=a+b*k,residual_mean=statistics.mean(contents)-a-b*k))
    passed = [doses[0]["content_mean"] >= 200,abs(a) <= 54,all(abs(d["residual_mean"]) <= 54 for d in doses)]
    groups = [[t["content"] for t in triples if t["dose"] == k] for k in range(1,5)]
    pure_error = sum((c-statistics.mean(g))**2 for g in groups for c in g)
    lack_of_fit = sum((yy-a-b*xx)**2 for xx,yy in zip(x,y))-pure_error
    lack_of_fit_f = (lack_of_fit/2)/(pure_error/16) if pure_error > 0 else None
    return dict(triples=triples,doses=doses,a=a,b=b,se_a=residual_sd*math.sqrt(1/20+xm*xm/sxx),
                se_b=residual_sd/math.sqrt(sxx),residual_sd=residual_sd,degenerate_fit=residual_sd == 0,
                lack_of_fit_f=lack_of_fit_f,lack_of_fit_df=[2,16],
                pass_items={str(i+1):v for i,v in enumerate(passed)},verdict="PASS" if all(passed) else "FAIL")


def dose_response(runner):
    block_path = HERE/"samples"/"dose-block.txt"
    reports = []
    doubled = False
    for attempt in range(2):
        block = block_path.read_bytes()
        block.decode("ascii")
        order = [(k,index) for k in range(1,5) for index in range(5)]
        random.Random(runner.config["seed"]).shuffle(order)
        values = []
        for position,(dose,index) in enumerate(order):
            row = triples(runner,{"CLAUDE.md":block*dose},{},"dose","AN",count=1,
                          metadata=dict(dose=dose,dose_repeat=index,dose_attempt=attempt,round=position))[0]
            row.update(dose=dose,dose_repeat=index,batch_position=position)
            values.append(row)
        report = dose_stats(values)
        report.update(block_md5=r.md5(block_path),attempt=attempt,block_doubled=doubled)
        reports.append(report)
        r.dump(runner.logs/(runner.batch_id+f"-dose-attempt-{attempt}.json"),report)
        print(json.dumps(report,sort_keys=True,indent=2),flush=True)
        if report["pass_items"]["1"] or attempt == 1:
            break
        block_path.write_bytes(block+block)
        doubled = True
        new_hash = r.md5(block_path)
        print("DOSE BLOCK DOUBLED ONCE; MD5: "+new_hash,flush=True)
        recipe = HERE/"environment-recipe.md"
        with recipe.open("a",encoding="utf-8",newline="\n") as f:
            f.write("\nDose-response item 1 shortfall: doubled B once; new dose-block.txt MD5: "+new_hash+"\n")
    return dict(attempts=reports,block_doubled=doubled,verdict=reports[-1]["verdict"])


def valid(record):
    """A run counts only without a cost assertion and without a permission denial (A48)."""
    return not ({"cost_assertion", "permission_denied"} & set(record["flags"]))


def schema():
    return ["run_id","track","batch_id","task_or_fixture_id","arm","model_id","claude_version","harness_md5","runlib_md5","pricing_md5","seed","round","position","start_time","gap_since_previous_same_arm","config_dir","working_dir","config_dir_hash","expected_skills","observed_skills","observed_plugins","observed_mcp_servers","skill_calls","temp_leftovers","edit_evidence","auxiliary_models","usage.input_tokens","usage.output_tokens","usage.cache_creation_input_tokens","usage.cache_read_input_tokens","cache_write_5m","cache_write_1h","total_cost_usd","modelUsage","computed_cost_per_model","computed_cost_total","unit_rates","cost_assertion_difference","cache_read_share","triggered","turn_count","duration_ms","check_exit_code","check_reason","deletion_assertions","credential_check","flags","triples","probe_results","first_pass_score","second_pass_score","scored_at_unedited_size","shell_tool","configured_tool_set","observed_tools","shell_tool_confirmed","permission_flags","containment","permission_denials","launcher","config_files","event_counts"]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command",choices=["run-task","run-edit","triples","probes","batch","dry-run","selftest","dose-response"])
    p.add_argument("--config",type=Path,default=HERE/"config.example.json")
    p.add_argument("--task",default="T01")
    p.add_argument("--fixture",default="F2")
    p.add_argument("--arm",default="N")
    p.add_argument("--manifest",type=Path)
    args = p.parse_args(argv)
    c = load_config(args.config)
    if args.command == "selftest":
        outcome = r.child(c,[sys.executable,"-B","-m","pytest","-q",str(HERE/"test_harness.py")])
        print(outcome.stdout,end="")
        print(outcome.stderr,end="",file=sys.stderr)
        return outcome.returncode
    logs = Path(c["log_root"])/"dose" if args.command == "dose-response" else Path(c["log_root"])
    runner = None
    try:
        runner = r.Runner(c,log_dir=logs)
        if args.command == "run-task":
            output = run_task(runner,args.task,args.arm)
        elif args.command == "run-edit":
            output = track_a(runner,args.fixture,args.arm)
        elif args.command in ("triples","probes"):
            fixture = Path(c["eval_root"])/"fixtures"/args.fixture
            files, skills = r.fixture_files(fixture),skill_set(c,args.arm,fixture)
            output = triples(runner,files,skills,args.fixture,args.arm) if args.command == "triples" else probes(runner,args.fixture,args.arm,files,skills)
        elif args.command == "dry-run":
            task = run_task(runner,"T01","N")
            fixture = track_a(runner,"F2","AN",dry_run=True)
            output = dict(task_run_id=task["run_id"],task_check=task["check_exit_code"],
                          track_a_run_id=fixture["run_id"],probe_score=fixture["first_pass_score"],
                          auxiliary_model_runs=sum(bool(record.get("auxiliary_models")) for record in runner.records),
                          permission_denied_runs=sum("permission_denied" in record["flags"] for record in runner.records),
                          schema=schema(),log_paths=[str(p) for p in sorted(runner.logs.glob(runner.batch_id+"*"))])
            r.dump(runner.logs/(runner.batch_id+"-dry-summary.json"),output)
        elif args.command == "dose-response":
            output = dose_response(runner)
        else:
            if args.manifest is None:
                raise r.RunError("batch requires --manifest")
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            output = []
            for task in manifest["tasks"]:
                for round_id,position,arm in r.block_order(manifest["arms"],manifest["rounds"],c["seed"]):
                    meta = dict(round=round_id,position=position)
                    if manifest["track"] == "B":
                        output.append(run_task(runner,task,arm,meta))
                    else:
                        output.append(track_a(runner,task,arm,metadata=meta))
            cells = {}
            for record in output:
                key = (record["task_or_fixture_id"],record["arm"])
                cells.setdefault(key,[]).append(record)
            if any(not any(valid(record) for record in records) for records in cells.values()):
                raise r.RunError("task-and-arm cell has no valid run left")
        if args.command == "dose-response":
            output["auxiliary_model_runs"] = sum(bool(record.get("auxiliary_models")) for record in runner.records)
        print(json.dumps(output,sort_keys=True,indent=2),flush=True)
        return 0
    except Exception as exc:
        message = r.redact(str(exc).encode(),c["credentials_file"]).decode()
        print("HARNESS FAILED: "+message,file=sys.stderr,flush=True)
        return 1
    finally:
        if runner:
            runner.checkpoint()


if __name__ == "__main__":
    raise SystemExit(main())

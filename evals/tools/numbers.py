"""Compute numbers.json (confirmatory and exploratory keys) from the final records.

Usage: python numbers.py --records R --prereg P --analysis-py A --out numbers.json
       [--figures-spec finalmd-figures.json --check] [--expect-analysis PATH]
       [--mutation-test EXPLIST]
"""
import os
import sys

# This file is named numbers.py and would shadow the standard library module of that name
# (imported by numpy), so the script directory is removed from the import path first.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != _HERE]

import argparse
import copy
import fnmatch
import gzip
import importlib.util
import json
import math
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

COMPARISONS = ["K1 against K0", "K1 against N", "N against K0", "K1f against K0f", "K0f against K0"]
B_ARMS = ["K0", "K0f", "K1", "K1f", "N"]
A_ARMS = ["AN", "AS", "ASn"]
MODEL = "claude-sonnet-5-5"
DEV_ESTIMATE = -0.070612
E5_SEED = 20261111
E5_DRAWS = 200000


def ckey(name):
    return name.replace(" against ", "_vs_")


def load_records(path):
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    out = []
    with opener(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                out.append(json.loads(line))
    return out


def load_analysis(path):
    spec = importlib.util.spec_from_file_location("analysis_under_test", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render_analysis(result):
    return json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n"


def single(values, what):
    values = set(values)
    if len(values) != 1:
        raise ValueError(f"{what} differ: {sorted(values)}")
    return values.pop()


def compute(records, prereg, analysis):
    """Return (flat numbers dict key -> (value, source, method or None), analysis result)."""
    A = analysis.analyse(records, prereg, "final")
    c = A["constants"]
    out = {}

    def put(key, value, source, method=None):
        if isinstance(value, (np.floating, np.integer)):
            value = value.item()
        if isinstance(value, bool):
            value = int(value)
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError(f"non-finite value for {key}")
        out[key] = (value, source, method)

    B = [r for r in records if r["track"] == "B"]
    TA = [r for r in records if r["track"] == "A" and "triples" in r]
    arm_runs = defaultdict(list)
    for r in B:
        arm_runs[r["arm"]].append(r)

    # comparisons
    for name in COMPARISONS:
        comp = A["task_comparisons"][name]
        k = ckey(name)
        p = comp["primary"]
        base = f"confirmatory.comparison.{k}"
        src = f'task_comparisons["{name}"].primary'
        put(f"{base}.mean", p["mean"], src + ".mean")
        put(f"{base}.ratio", math.exp(p["mean"]), "exp(" + src + ".mean)")
        put(f"{base}.lo", p["interval"][0], src + ".interval[0]")
        put(f"{base}.hi", p["interval"][1], src + ".interval[1]")
        put(f"{base}.p", p["p"], src + ".p")
        if name == "K0f against K0":
            put(f"{base}.percent_increase", (math.exp(p["mean"]) - 1) * 100, "(exp(primary.mean)-1)*100")
        if name == "K1 against K0":
            ca = comp["cache_adjusted_sensitivity"]
            put(f"{base}.cache_adjusted.mean", ca["mean"], src.replace("primary", "cache_adjusted_sensitivity") + ".mean")
            put(f"{base}.cache_adjusted.lo", ca["interval"][0], "cache_adjusted_sensitivity.interval[0]")
            put(f"{base}.cache_adjusted.hi", ca["interval"][1], "cache_adjusted_sensitivity.interval[1]")

    # constants
    for key in ("minimum_effect", "preregistered_r", "comparator", "as_target"):
        put(f"confirmatory.constants.{key}", c[key], f"constants.{key}")
    put("confirmatory.constants.probe_threshold_F2", min(c["probe_thresholds"]["F2"]), "min(constants.probe_thresholds.F2)")
    put("confirmatory.constants.unedited_F2", c["unedited_content_tokens"]["F2"], "constants.unedited_content_tokens.F2")
    put("confirmatory.constants.target_reduction_percent", (1 - c["as_target"]) * 100, "(1-as_target)*100")

    # counts
    cells_b = defaultdict(list)
    for r in B:
        cells_b[r["task_or_fixture_id"], r["arm"]].append(r)
    put("confirmatory.counts.records", len(records), "count of all records")
    put("confirmatory.counts.batches", len({r["batch_id"] for r in records}), "distinct batch_id")
    put("confirmatory.counts.track_b_records", len(B), "records with track B")
    put("confirmatory.counts.track_a_records", len(TA), "track A records with triples")
    put("confirmatory.counts.track_b_batches", len({r["batch_id"] for r in B}), "distinct batch_id among track B")
    put("confirmatory.counts.track_b_cells", len(cells_b), "distinct (task, arm) among track B")
    put("confirmatory.counts.runs_per_cell", single((len(v) for v in cells_b.values()), "cell sizes"), "single track B cell size")
    put("confirmatory.counts.tasks", len({t for t, _ in cells_b}), "distinct track B tasks")
    put("confirmatory.counts.track_b_arms", len(arm_runs), "distinct track B arms")
    put("confirmatory.counts.runs_per_arm", single((len(v) for v in arm_runs.values()), "track B runs per arm"), "track B runs per arm")
    ta_arms = defaultdict(list)
    for r in TA:
        ta_arms[r["arm"]].append(r)
    put("confirmatory.counts.runs_per_track_a_arm", single((len(v) for v in ta_arms.values()), "track A runs per arm"), "track A runs per arm (with triples)")
    put("confirmatory.counts.cost_flagged", sum(bool(r.get("cost_flagged")) for r in records), "records with truthy cost_flagged")
    put("confirmatory.counts.voided", sum(bool(r["flags"]) for r in records), "records with non-empty flags")

    # batch cost
    put("confirmatory.batch_cost.total", sum(r["total_cost_usd"] for r in records), "sum total_cost_usd, all records")
    put("confirmatory.batch_cost.track_b", sum(r["total_cost_usd"] for r in B), "sum total_cost_usd, track B")
    put("confirmatory.batch_cost.track_a", sum(r["total_cost_usd"] for r in records if r["track"] == "A"), "sum total_cost_usd, track A")

    for arm in B_ARMS:
        runs = arm_runs[arm]
        put(f"confirmatory.mean_cost_per_run.{arm}", sum(r["computed_cost_total"] for r in runs) / len(runs), "mean computed_cost_total, track B")
        d = A["descriptive"][f"{arm}/{MODEL}"]
        put(f"confirmatory.descriptive.{arm}.cost_all", d["cost_all"], f'descriptive["{arm}/{MODEL}"].cost_all')
        put(f"confirmatory.descriptive.{arm}.cost_passing", d["cost_passing"], f'descriptive["{arm}/{MODEL}"].cost_passing')

    shares = [A["descriptive"][f"{arm}/{MODEL}"]["cache_read_share"] for arm in B_ARMS]
    put("confirmatory.cache_read_share.min", min(shares), "min descriptive cache_read_share over track B arms")
    put("confirmatory.cache_read_share.max", max(shares), "max descriptive cache_read_share over track B arms")
    for arm in B_ARMS:
        put(f"confirmatory.cache_read_share.{arm}", A["descriptive"][f"{arm}/{MODEL}"]["cache_read_share"],
            f'descriptive["{arm}/{MODEL}"].cache_read_share')

    # successes
    passing = {arm: sum(r["check_exit_code"] == 0 for r in arm_runs[arm]) for arm in B_ARMS}
    put("confirmatory.successes.min_per_arm", min(passing.values()), "min passing runs (check_exit_code 0) per track B arm")
    put("confirmatory.successes.max_abs_success_difference",
        max(abs(x) for n in COMPARISONS for x in A["task_comparisons"][n]["success_differences"]),
        "max abs success_differences over five comparisons")

    # triggers
    for arm in B_ARMS:
        put(f"confirmatory.triggers.{arm}", sum(bool(r["triggered"]) for r in arm_runs[arm]), "triggered track B runs")
    for arm in A_ARMS:
        put(f"confirmatory.triggers.{arm}", sum(bool(r["triggered"]) for r in ta_arms[arm]), "triggered track A runs with triples")
    lo, hi = A["context"]["verdicts"]["F2"]["trigger"]["interval"]
    put("confirmatory.triggers.ASn_interval_lo", lo, "context.verdicts.F2.trigger.interval[0]")
    put("confirmatory.triggers.ASn_interval_hi", hi, "context.verdicts.F2.trigger.interval[1]")

    # rule 4
    arm_of = {r["run_id"]: r["arm"] for r in TA}
    details = analysis.context_runs(records, c)["runs"]
    sizes = defaultdict(list)
    excess, n_unedited = 0.0, 0
    for d in details:
        unedited = c["unedited_content_tokens"][d["fixture"]]
        if d["scored_at_unedited_size"]:
            size = float(unedited)
            n_unedited += 1
            excess += unedited - d["mean"]
        else:
            size = d["mean"]
        sizes[arm_of[d["run_id"]]].append(size)
    for arm in A_ARMS:
        x = np.asarray(sizes[arm], dtype=float)
        put(f"confirmatory.rule4.{arm}.mean", float(x.mean()), "mean scored size, track A runs (context_runs)")
        put(f"confirmatory.rule4.{arm}.sd", float(x.std(ddof=1)), "sd (ddof 1) of scored size, track A runs")
    an_mean, as_mean = float(np.mean(sizes["AN"])), float(np.mean(sizes["AS"]))
    ratio = as_mean / an_mean
    put("confirmatory.rule4.ratio", ratio, "AS mean / AN mean")
    put("confirmatory.rule4.reduction_percent", (1 - ratio) * 100, "(1-ratio)*100")
    wel = A["context"]["verdicts"]["F2"]["rule4"]
    put("confirmatory.rule4.welch_t", wel["t"], "context.verdicts.F2.rule4.t")
    put("confirmatory.rule4.df", wel["df"], "context.verdicts.F2.rule4.df")
    put("confirmatory.rule4.p", wel["p"], "context.verdicts.F2.rule4.p")
    r4 = analysis.rule4_from_sizes(sizes["AN"], c)
    put("confirmatory.rule4.cv", r4["cv"], "rule4_from_sizes(AN).cv")
    put("confirmatory.rule4.upper_cv", r4["upper_cv"], "rule4_from_sizes(AN).upper_cv")
    put("confirmatory.rule4.r_required", r4["rule4_r"], "rule4_from_sizes(AN).rule4_r")
    kw = dict(alpha=c["alpha"], target=c["as_target"], comparator=c["comparator"])
    put("confirmatory.rule4.power_at_cv", analysis.rule4_power(c["preregistered_r"], r4["cv"], **kw), "rule4_power(preregistered_r, cv)")
    put("confirmatory.rule4.power_at_upper_cv", analysis.rule4_power(c["preregistered_r"], r4["upper_cv"], **kw), "rule4_power(preregistered_r, upper_cv)")
    put("confirmatory.rule4.AN.cut_percent", (1 - an_mean / c["unedited_content_tokens"]["F2"]) * 100, "(1-AN mean/unedited_F2)*100")
    put("confirmatory.rule4.scored_unedited_count", n_unedited, "track A runs scored at unedited size")
    put("confirmatory.rule4.unedited_excess_tokens", excess, "sum(unedited size - triple mean) over runs scored at unedited size")

    # run 0123
    hits = [r for r in TA if r["run_id"].endswith("-0123")]
    if len(hits) != 1:
        raise ValueError(f"expected one track A run ending -0123, found {len(hits)}")
    h = hits[0]
    put("confirmatory.run_0123.first_pass_score", h["first_pass_score"], "record first_pass_score")
    put("confirmatory.run_0123.second_pass_score", h["second_pass_score"], "record second_pass_score")
    tm = [d["mean"] for d in details if d["run_id"] == h["run_id"]]
    put("confirmatory.run_0123.triple_mean", tm[0], "context.runs mean")

    # ---- exploratory ----
    def exp(key, value, source, method):
        put(f"exploratory.{key}", value, source, method)

    # E1
    kn = A["task_comparisons"]["K1 against N"]["differences"]
    x = np.asarray(kn, dtype=float)
    se = x.std(ddof=1) / math.sqrt(len(x))
    crit = stats.t.ppf(0.95, len(x) - 1)
    lo, hi = float(x.mean() - crit * se), float(x.mean() + crit * se)
    m = max(abs(lo), abs(hi))
    base = "equivalence.K1_vs_N"
    src = "two-sided 90 per cent t interval (df 11) of K1 against N per-task log differences"
    exp(f"{base}.lo", lo, src, "E1")
    exp(f"{base}.hi", hi, src, "E1")
    exp(f"{base}.ratio_lo", math.exp(lo), "exp(lo)", "E1")
    exp(f"{base}.ratio_hi", math.exp(hi), "exp(hi)", "E1")
    exp(f"{base}.margin_log", m, "max(|lo|,|hi|)", "E1")
    exp(f"{base}.margin_ratio", math.exp(m), "exp(margin_log)", "E1")

    # E2
    groups = defaultdict(list)
    for r in records:
        groups[r["arm"]].append(r)
    for arm in sorted(groups):
        comp = dict(input=0.0, cache_read=0.0, cache_write=0.0, output=0.0)
        cost = 0.0
        for r in groups[arm]:
            cost += r["computed_cost_total"]
            for model, u in r["modelUsage"].items():
                rates = r["unit_rates"][model]
                comp["input"] += u["inputTokens"] * rates["input"]
                comp["cache_read"] += u["cacheReadInputTokens"] * rates["read"]
                comp["cache_write"] += u["cacheCreationInputTokens"] * analysis.write_rate(r, rates)
                comp["output"] += u["outputTokens"] * rates["output"]
        total = sum(comp.values())
        base = f"cost_decomposition.{arm}"
        s = "sum of tokens x unit_rates over runs and models"
        for k, v in comp.items():
            exp(f"{base}.{k}", v, s, "E2")
            exp(f"{base}.share_{k}", v / total, f"{k} / decomposition total", "E2")
        exp(f"{base}.total", total, "sum of the four components", "E2")
        exp(f"{base}.residual", cost - total, "sum computed_cost_total minus decomposition total", "E2")

    # E3
    for name in COMPARISONS:
        comp = A["task_comparisons"][name]
        for t, d in zip(comp["tasks"], comp["differences"]):
            exp(f"forest.{ckey(name)}.{t}", d, f'task_comparisons["{name}"].differences', "E3")
    for arm in B_ARMS:
        for (t, a), runs in sorted(cells_b.items()):
            if a == arm:
                exp(f"forest.cost_per_success.{arm}.{t}", analysis.cost_success(runs, 0.5), "log cost per success, divisor 0.5", "E3")

    # E4
    seed = c["within_seed"]
    for name in COMPARISONS:
        cand, compa = name.split(" against ")
        comp = A["task_comparisons"][name]
        rng = np.random.default_rng(seed)
        within = []
        for t in comp["tasks"]:
            arms = [cells_b[t, cand], cells_b[t, compa]]
            sim = []
            for _ in range(c["within_resamples"]):
                samples = [[a[i] for i in rng.integers(0, len(a), len(a))] for a in arms]
                sim.append(analysis.cost_success(samples[0], c["zero_pass_divisor"]) - analysis.cost_success(samples[1], c["zero_pass_divisor"]))
            within.append(float(np.var(sim, ddof=1)))
        w = float(np.mean(within))
        tot = float(np.var(comp["differences"], ddof=1))
        between = max(0.0, tot - w)
        base = f"variance.{ckey(name)}"
        s = "bootstrap within-task variance, 2000 resamples, seed within_seed"
        exp(f"{base}.within", w, s + "; mean over tasks", "E4")
        exp(f"{base}.between", between, "max(0, var(differences) - within)", "E4")
        exp(f"{base}.total", tot, "sample variance (ddof 1) of the per-task differences", "E4")
        exp(f"{base}.between_share", between / tot if tot else 0.0, "between / total", "E4")

    # E5
    sd = float(np.std(A["task_comparisons"]["K1 against K0"]["differences"], ddof=1))
    n_tasks = len(A["task_comparisons"]["K1 against K0"]["differences"])
    crit = stats.t.ppf(1 - c["alpha"], n_tasks - 1)
    bar = c["minimum_effect"]
    rng = np.random.default_rng(E5_SEED)

    def mc(effect):
        d = rng.normal(effect, sd, size=(E5_DRAWS, n_tasks))
        mean = d.mean(axis=1)
        se_ = d.std(axis=1, ddof=1) / math.sqrt(n_tasks)
        sig = mean + crit * se_ < 0
        return float(sig.mean()), float((sig & (mean <= bar)).mean())

    exp("power_rule1.sd", sd, "SD (ddof 1) of K1 against K0 per-task differences", "E5")
    for i in range(-300, 51, 5):
        eff = i / 1000
        exp(f"power_rule1.curve.{eff:.3f}", mc(eff)[1], f"Monte Carlo rule 1 pass probability at effect {eff:.3f}", "E5")
    exp("power_rule1.test_only_at_bar", mc(bar)[0], "Monte Carlo power of the t test alone at the bar", "E5")
    exp("power_rule1.at_bar", mc(bar)[1], "Monte Carlo rule 1 pass probability at the bar", "E5")
    exp("power_rule1.at_dev_estimate", mc(DEV_ESTIMATE)[1], "Monte Carlo rule 1 pass probability at -0.070612", "E5")

    # E6
    pos = defaultdict(list)
    pc = defaultdict(list)
    for r in records:
        if r["track"] != "B":
            continue
        pos[r["arm"]].append(r["position"])
        pc[r["arm"], r["position"]].append(r["computed_cost_total"])
    tapos = defaultdict(list)
    for r in records:
        if r["track"] == "A" and "triples" in r:
            tapos[r["arm"]].append(r["position"])
    for arm in sorted(tapos):
        put(f"confirmatory.track_a_position_mean.{arm}", sum(tapos[arm]) / len(tapos[arm]), "mean position over track A runs with triples (final.md line 53)")
    for arm in sorted(pos):
        exp(f"arm_position.mean.{arm}", sum(pos[arm]) / len(pos[arm]), "mean position", "E6")
    for (arm, p), v in sorted(pc.items()):
        exp(f"arm_position.cost.{arm}.p{p}", sum(v) / len(v), "mean computed_cost_total per run", "E6")

    return out, A


def to_json_object(flat):
    obj = {}
    for key in sorted(flat):
        value, source, method = flat[key]
        item = {"value": value, "source": source}
        if key.startswith("exploratory."):
            item["exploratory"] = True
            item["method"] = method
        obj[key] = item
    return obj


def render_numbers(flat):
    return json.dumps(to_json_object(flat), sort_keys=True, indent=1, allow_nan=False) + "\n"


def run_check(flat, spec_path):
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    tokens = [t for t in spec["tokens"] if t["label"] == "key"]
    keys, n_ok, failures = set(), 0, []
    for t in tokens:
        ok = True
        text = t["token"].replace(",", "")
        d = len(text.split(".")[1]) if "." in text else 0
        target = float(text)
        for k in t["keys"]:
            keys.add(k)
            if k not in flat:
                failures.append(f"FAIL line {t['line']} token {t['token']} key {k} value MISSING")
                ok = False
                continue
            v = flat[k][0]
            if round(float(v), d) != target:
                failures.append(f"FAIL line {t['line']} token {t['token']} key {k} value {v}")
                ok = False
        n_ok += ok
    print(f"CHECK {n_ok} of {len(tokens)} tokens, {len(keys)} keys")
    for f in failures:
        print(f)
    return not failures


def parse_mutation(path):
    text = Path(path).read_text(encoding="utf-8")
    section = text.split("## One-record mutation test", 1)[1]
    rid = re.search(r"Record `([^`]+)`", section).group(1)
    mut_line = re.search(r"Mutation:([^\n]*)", section).group(1)
    factor = float(re.search(r"by (\d+(?:\.\d+)?)", mut_line).group(1))
    fields = re.findall(r"`([^`]+)`", mut_line)
    patterns = re.findall(r"^- `([^`]+)`\s*$", section, flags=re.M)
    return rid, fields, factor, patterns


def mutate(records, rid, fields, factor):
    out = copy.deepcopy(records)
    hit = [r for r in out if r["run_id"] == rid]
    if len(hit) != 1:
        raise ValueError(f"record {rid} found {len(hit)} times")
    r = hit[0]
    for f in fields:
        m = re.fullmatch(r'(\w+)(?:\["([^"]+)"\])?', f)
        if m.group(2):
            r[m.group(1)][m.group(2)] *= factor
        else:
            r[m.group(1)] *= factor
    return out


def run_mutation(records, prereg, analysis, base_flat, explist):
    rid, fields, factor, patterns = parse_mutation(explist)
    mflat, _ = compute(mutate(records, rid, fields, factor), prereg, analysis)
    if set(mflat) != set(base_flat):
        print("MUTATION FAIL key sets differ")
        return False
    changed = sorted(k for k in base_flat if base_flat[k][0] != mflat[k][0])
    bad = [k for k in changed if not any(fnmatch.fnmatchcase(k, p) for p in patterns)]
    unmatched = [p for p in patterns if not any(fnmatch.fnmatchcase(k, p) for k in changed)]
    if bad or unmatched:
        for k in bad:
            print(f"MUTATION FAIL unexpected change: {k}")
        for p in unmatched:
            print(f"MUTATION FAIL pattern matched no changed key: {p}")
        return False
    print(f"MUTATION PASS {len(changed)} keys changed")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", required=True)
    ap.add_argument("--prereg", required=True)
    ap.add_argument("--analysis-py", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--figures-spec")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--expect-analysis")
    ap.add_argument("--mutation-test")
    a = ap.parse_args()

    records = load_records(a.records)
    prereg = json.loads(Path(a.prereg).read_text(encoding="utf-8"))
    analysis = load_analysis(a.analysis_py)
    flat, A = compute(records, prereg, analysis)

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rendered_analysis = render_analysis(A)
    (out.parent / "analysis-recomputed.json").write_text(rendered_analysis, encoding="utf-8", newline="\n")
    out.write_text(render_numbers(flat), encoding="utf-8", newline="\n")
    print(f"wrote {out} ({len(flat)} keys)")

    ok = True
    if a.check:
        if not a.figures_spec:
            ap.error("--check needs --figures-spec")
        ok &= run_check(flat, a.figures_spec)
    if a.expect_analysis:
        if Path(a.expect_analysis).read_bytes() == rendered_analysis.encode("utf-8"):
            print("ANALYSIS IDENTICAL")
        else:
            print("ANALYSIS DIFFERENT")
            ok = False
    if a.mutation_test:
        ok &= run_mutation(records, prereg, analysis, flat, a.mutation_test)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

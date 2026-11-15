"""Deterministic analysis of token-aware evaluation records; no network access."""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

CONSTANTS = dict(alpha=0.025, minimum_effect=math.log(0.85), quality_margin=0.10,
                 zero_pass_divisor=0.5, sentinel_divisor=1.0, as_target=0.85,
                 comparator=0.9, detection_difference=0.05, power=0.80,
                 chi_square_coverage=0.80, bootstrap_resamples=10000,
                 within_resamples=2000, repeats=[3, 5, 8, 10])


def sd_upper_factor(df, coverage=0.80):
    if df <= 0 or not 0 < coverage < 1:
        raise ValueError("positive degrees of freedom and coverage in (0,1) required")
    return math.sqrt(df / stats.chi2.ppf(1 - coverage, df))


def sd_upper(values, coverage=0.80):
    return float(np.std(values, ddof=1)) * sd_upper_factor(len(values)-1, coverage)


def paired(values, alpha=0.025):
    x = np.asarray(values, dtype=float)
    if len(x) < 2 or not np.all(np.isfinite(x)):
        return dict(pass_test=False, reason="at least two finite task values required")
    mean, sd = float(x.mean()), float(x.std(ddof=1))
    se = sd / math.sqrt(len(x))
    crit = stats.t.ppf(1-alpha, len(x)-1)
    if se:
        t = mean / se
        p = float(stats.t.cdf(t, len(x)-1))
    else:
        t, p = None, (0.0 if mean < 0 else 1.0)
    return dict(mean=mean, sd=sd, se=se, df=len(x)-1, t=t, p=p,
                interval=[mean-float(crit)*se, mean+float(crit)*se],
                pass_test=bool(mean+crit*se < 0))


def bootstrap(values, seed, resamples=10000):
    x = np.asarray(values, dtype=float)
    if len(x) == 0:
        raise ValueError("empty bootstrap")
    rng = np.random.default_rng(seed)
    means = x[rng.integers(0, len(x), size=(resamples, len(x)))].mean(axis=1)
    return dict(seed=seed, resamples=resamples,
                interval=np.quantile(means, [0.025, 0.975]).tolist(),
                label="limited: few distinct resamples")


def clopper_pearson(k, r):
    if not 0 <= k <= r or r < 1:
        raise ValueError("invalid binomial counts")
    return [0.0 if k == 0 else float(stats.beta.ppf(.025, k, r-k+1)),
            1.0 if k == r else float(stats.beta.ppf(.975, k+1, r-k))]


def paired_power(n, sd, effect=.1625, alpha=.025):
    if sd == 0:
        return 1.0
    return float(stats.nct.sf(stats.t.ppf(1-alpha, n-1), n-1,
                              effect*math.sqrt(n)/sd))


def smallest_n(sd, effect, power=.80, alpha=.025):
    if sd < 0 or effect <= 0 or not 0 < power < 1 or not 0 < alpha < 1:
        raise ValueError("invalid power parameters")
    for n in range(2, 100001):
        if paired_power(n, sd, effect, alpha) >= power:
            return n
    raise ValueError("required task count exceeds 100000")


def rule4_power(r, bounded_cv, alpha=.025, target=.85, comparator=.9):
    """Power for a CV already set to its upper 80 percent bound."""
    cv = bounded_cv
    v1, v2 = (cv*target)**2/r, (cv*comparator)**2/r
    if v1+v2 == 0:
        return 1.0
    df = (v1+v2)**2 / ((v1*v1+v2*v2)/(r-1))
    ncp = (comparator-target) / math.sqrt(v1+v2)
    return float(stats.nct.sf(stats.t.ppf(1-alpha, df), df, ncp))


def rule4_r(bounded_cv, power=.80, **kwargs):
    for r in range(2, 100001):
        if rule4_power(r, bounded_cv, **kwargs) >= power:
            return r
    raise ValueError("required repeats exceed 100000")


def welch_rule4(candidate, comparator, required_r, alpha=.025, scale=.9):
    x, y = np.asarray(candidate), np.asarray(comparator)*scale
    if min(len(x), len(y)) < required_r:
        return dict(pass_test=False, reason="underpowered")
    if min(len(x), len(y)) < 2:
        return dict(pass_test=False, reason="at least two runs per arm required")
    vx, vy = float(x.var(ddof=1))/len(x), float(y.var(ddof=1))/len(y)
    if vx+vy == 0:
        return dict(pass_test=False, reason="both arms have zero variance")
    df = (vx+vy)**2 / (vx*vx/(len(x)-1)+vy*vy/(len(y)-1))
    t = float(x.mean()-y.mean()) / math.sqrt(vx+vy)
    p = float(stats.t.cdf(t, df))
    return dict(t=t, df=df, p=p, pass_test=p < alpha)


def write_rate(record, rates):
    """Blended cache-write rate from the record's 5-minute and 1-hour split (pricing.py unit_rates)."""
    five, hour = record["cache_write_5m"], record["cache_write_1h"]
    if five + hour == 0:
        return rates["write_5m"]
    return (five*rates["write_5m"]+hour*rates["write_1h"])/(five+hour)


def cost_success(runs, divisor=.5, shared_cache=None):
    costs = []
    for r in runs:
        value = r["computed_cost_total"]
        if shared_cache is not None:
            value = 0.0
            for model, u in r["modelUsage"].items():
                rates = r["unit_rates"][model]
                total = u["inputTokens"]+u["cacheReadInputTokens"]+u["cacheCreationInputTokens"]
                nonread = u["inputTokens"]+u["cacheCreationInputTokens"]
                write_fraction = u["cacheCreationInputTokens"]/nonread if nonread else 0.0
                value += total*shared_cache*rates["read"]
                value += total*(1-shared_cache)*((1-write_fraction)*rates["input"]+write_fraction*write_rate(r, rates))
                value += u["outputTokens"]*rates["output"]
        costs.append(value)
    n = sum(r["check_exit_code"] == 0 for r in runs)
    amount = sum(costs)/(n or divisor)
    if amount <= 0:
        raise ValueError("nonpositive cost per success")
    return math.log(amount)


def validate(records, prereg):
    if not records:
        raise ValueError("no input records")
    flagged, voided = defaultdict(int), defaultdict(int)
    cells, valid_cells, valid = set(), set(), []
    for r in records:
        for key in ("claude_version", "model_id", "harness_md5", "runlib_md5", "pricing_md5"):
            if key not in prereg:
                raise ValueError(f"missing prereg pin: {key}")
            if r[key] != prereg[key]:
                raise ValueError(f"{key} mismatch in {r['run_id']}")
        cell = (r["track"], r["task_or_fixture_id"], r["arm"])
        cells.add(cell)
        flagged[r["batch_id"]] += 0
        voided[r["batch_id"]] += 0
        if "cost_assertion" in r["flags"]:
            flagged[r["batch_id"]] += 1
        elif "permission_denied" in r["flags"]:
            voided[r["batch_id"]] += 1  # A48: a denied run is void and enters no endpoint (harness.valid)
        else:
            valid.append(r)
            valid_cells.add(cell)
    if cells - valid_cells:
        raise ValueError(f"no valid run in cells: {sorted(cells-valid_cells)}; flagged={dict(flagged)}")
    expected = {tuple(cell) for cell in prereg.get("expected_cells", [])}
    if expected - valid_cells:
        raise ValueError(f"missing preregistered cells: {sorted(expected-valid_cells)}")
    if any(n > prereg["exclusion_cap"] for n in flagged.values()):
        raise ValueError(f"cost exclusion cap exceeded: {dict(flagged)}")
    if "void_cap" in prereg and any(n > prereg["void_cap"] for n in voided.values()):
        raise ValueError(f"void cap exceeded: {dict(voided)}")
    return valid, dict(sorted(flagged.items())), dict(sorted(voided.items()))


def describe(runs):
    fields = ["input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"]
    tokens = {k: sum(r["usage"][k] for r in runs) for k in fields}
    total = sum(tokens[k] for k in fields if k != "output_tokens")
    uncached = 0.0
    for r in runs:
        for model, u in r["modelUsage"].items():
            rates = r["unit_rates"][model]
            uncached += (u["inputTokens"]+u["cacheReadInputTokens"]+u["cacheCreationInputTokens"])*rates["input"]+u["outputTokens"]*rates["output"]
    return dict(cost_all=sum(r["computed_cost_total"] for r in runs),
                cost_passing=sum(r["computed_cost_total"] for r in runs if r["check_exit_code"] == 0),
                tokens=tokens, uncached_equivalent_cost=uncached,
                trigger_rate=sum(r["triggered"] for r in runs)/len(runs),
                success_rate=sum(r["check_exit_code"] == 0 for r in runs)/len(runs),
                cache_read_share=tokens["cache_read_input_tokens"]/total if total else 0.0)


def task_comparison(cells, candidate, comparator, c):
    tasks = sorted({t for t, a in cells if a in (candidate, comparator)})
    if any((t, a) not in cells for t in tasks for a in (candidate, comparator)):
        raise ValueError("missing compared task-and-arm cell")
    d, sentinel, quality, excluded, kept, sens = [], [], [], [], [], []
    no_pass = 0
    arms = {a: [r for t in tasks for r in cells[t, a]] for a in (candidate, comparator)}
    shared = sum(describe(arms[a])["cache_read_share"] for a in arms)/2
    for t in tasks:
        x, y = cells[t, candidate], cells[t, comparator]
        nx, ny = sum(r["check_exit_code"] == 0 for r in x), sum(r["check_exit_code"] == 0 for r in y)
        delta = cost_success(x, c["zero_pass_divisor"])-cost_success(y, c["zero_pass_divisor"])
        d.append(delta)
        sentinel.append(cost_success(x, c["sentinel_divisor"])-cost_success(y, c["sentinel_divisor"]))
        sens.append(cost_success(x, c["zero_pass_divisor"], shared)-cost_success(y, c["zero_pass_divisor"], shared))
        quality.append(nx/len(x)-ny/len(y))
        no_pass += (nx == 0)+(ny == 0)
        if nx == 0 or ny == 0:
            excluded.append(t)
        else:
            kept.append(delta)
    primary, exclusion = paired(d, c["alpha"]), paired(kept, c["alpha"])
    practical = float(np.mean(d)) <= c["minimum_effect"]
    guard = paired(quality, c["alpha"])
    guard["pass_test"] = bool("interval" in guard and guard["interval"][0] > -c["quality_margin"])
    return dict(tasks=tasks, differences=d, success_differences=quality, primary=primary,
                exclusion=exclusion, excluded_task_ids=excluded, sentinel=paired(sentinel, c["alpha"]),
                practical_bar=f"{c['minimum_effect']:.4f}", practical_pass=practical,
                rule1_pass=primary["pass_test"] and exclusion["pass_test"] and practical,
                bootstrap=bootstrap(d, c["bootstrap_seed"], c["bootstrap_resamples"]),
                quality_guard=guard, no_pass_cells=no_pass,
                zero_pass_note="one extra passing run on a no-pass task moves the log difference by about 0.69",
                cache_adjusted_sensitivity=paired(sens, c["alpha"]))


def context_runs(records, c):
    groups = defaultdict(lambda: defaultdict(list))
    details = []
    skipped = defaultdict(int)
    for r in records:
        if r["track"] != "A" or "triples" not in r:
            continue
        if r["task_or_fixture_id"] not in c["probe_thresholds"]:
            skipped[r["task_or_fixture_id"]] += 1  # CR-01: F1's threshold lives in eval-private; F1 never gates (ADR-10)
            continue
        values = [t["FILE"]-t["BASE"]-t["WRAP"] for t in r["triples"]]
        if len(values) != 5:
            raise ValueError("context run must have five triples")
        fixture = r["task_or_fixture_id"]
        if r.get("dry_run"):
            raise ValueError("dry-run records are plumbing checks, not evaluation input")
        if len(c["probe_thresholds"][fixture]) != 5:
            raise ValueError("probe threshold requires five unedited scores")
        threshold = min(c["probe_thresholds"][fixture])
        first = r["first_pass_score"]
        second = r.get("second_pass_score")
        if first < threshold and second is None:
            raise ValueError("missing required second probe pass")
        fallback = first < threshold and second < threshold
        size = c["unedited_content_tokens"][fixture] if fallback else float(np.mean(values))
        groups[fixture][r["arm"]].append((size, bool(r["triggered"])))
        details.append(dict(run_id=r["run_id"], fixture=fixture, mean=float(np.mean(values)),
                            range=[min(values), max(values)], scored_at_unedited_size=fallback))
    verdicts = {}
    for fixture, arms in sorted(groups.items()):
        item = dict(label="in-sample; never gates" if fixture == "F1" else "gating")
        if "AS" in arms and "AN" in arms:
            item["rule4"] = welch_rule4([v[0] for v in arms["AS"]], [v[0] for v in arms["AN"]], c["preregistered_r"], c["alpha"], c["comparator"])
        if "ASn" in arms:
            k, n = sum(v[1] for v in arms["ASn"]), len(arms["ASn"])
            item["trigger"] = dict(k=k, r=n, interval=clopper_pearson(k, n))
        verdicts[fixture] = item
    return dict(runs=details, verdicts=verdicts, skipped_without_threshold=dict(sorted(skipped.items())),
                share_scored_at_unedited_size=sum(r["scored_at_unedited_size"] for r in details)/len(details) if details else None)


def rule4_from_sizes(sizes, c):
    """CR-01 extension: rule 4 runs per arm from an AN sample of any size n >= 2 (the CV bounded at its upper
    chi-square bound with n - 1 degrees of freedom), so r can be re-estimated from the S3 AN runs before the final batch."""
    x = np.asarray(sizes, dtype=float)
    if len(x) < 2 or not np.all(np.isfinite(x)) or x.mean() <= 0:
        raise ValueError("at least two finite positive AN sizes required")
    cv = float(np.std(x, ddof=1)/np.mean(x))
    bounded = cv*sd_upper_factor(len(x)-1, c["chi_square_coverage"])
    return dict(n=len(x), cv=cv, upper_cv=bounded,
                rule4_r=rule4_r(bounded, c["power"], alpha=c["alpha"], target=c["as_target"], comparator=c["comparator"]))


def per_model_descriptive(runs):
    groups = defaultdict(list)
    for r in runs:
        for model,u in r["modelUsage"].items():
            rec = dict(r)
            rec["modelUsage"] = {model:u}
            rec["computed_cost_total"] = r["computed_cost_per_model"][model]
            rec["usage"] = dict(input_tokens=u["inputTokens"],output_tokens=u["outputTokens"],
                                cache_creation_input_tokens=u["cacheCreationInputTokens"],
                                cache_read_input_tokens=u["cacheReadInputTokens"])
            groups[r["arm"],model].append(rec)
    return {f"{arm}/{model}":describe(values) for (arm,model),values in sorted(groups.items())}


def power_report(cells, comparison, records, c):
    d, q = comparison["differences"], comparison["success_differences"]
    rng = np.random.default_rng(c["within_seed"])
    within = []
    for t in comparison["tasks"]:
        arms = [cells[t, a] for a in ("N", "K0")]
        if any(len(a) != 5 for a in arms):
            raise ValueError("pilot power needs five runs per task and arm")
        simulated = []
        for _ in range(c["within_resamples"]):
            samples = [[a[i] for i in rng.integers(0, 5, 5)] for a in arms]
            simulated.append(cost_success(samples[0], c["zero_pass_divisor"])-cost_success(samples[1], c["zero_pass_divisor"]))
        within.append(float(np.var(simulated, ddof=1)))
    w = float(np.mean(within))
    between = max(0.0, float(np.var(d, ddof=1))-w)
    factor = sd_upper_factor(len(d)-1, c["chi_square_coverage"])
    quality_n = smallest_n(sd_upper(q, c["chi_square_coverage"]), c["quality_margin"], c["power"], c["alpha"])
    rows = []
    for r in c["repeats"]:
        sd = math.sqrt(between+w*5/r)
        n = smallest_n(sd*factor, abs(c["minimum_effect"]), c["power"], c["alpha"])
        held = max(n, quality_n)
        rows.append(dict(repeats=r, sd=sd, upper_sd=sd*factor, rule1_tasks=n,
                         rule2_tasks=quality_n, held_out_tasks=held,
                         required_pool=max(16, 2*held), pool_sufficient=c["pool_size"] >= max(16, 2*held)))
    an = []
    for r in records:
        if r["track"] == "A" and r["arm"] == "AN" and r["task_or_fixture_id"] == "F2" and "triples" in r:
            vals = [v["content"] for v in r["triples"]]
            threshold = min(c["probe_thresholds"]["F2"])
            fallback = r["first_pass_score"] < threshold and r["second_pass_score"] < threshold
            an.append(c["unedited_content_tokens"]["F2"] if fallback else float(np.mean(vals)))
    if len(an) != 5 or len(d) != 6:
        raise ValueError("pilot requires six tasks and five F2 AN runs")
    cv = float(np.std(an, ddof=1)/np.mean(an))
    bounded_cv = cv*sd_upper_factor(4, c["chi_square_coverage"])
    return dict(within_seed=c["within_seed"], within_variance=w, between_variance=between,
                task_counts=rows, pool_message="Adi chooses a larger pool or larger minimum effect if insufficient",
                pilot_cv=cv, upper_cv=bounded_cv,
                rule4_r=rule4_r(bounded_cv, c["power"], alpha=c["alpha"], target=c["as_target"], comparator=c["comparator"]),
                budget=[dict(r=r, task_runs=3*c["task_count"]*r,
                             task_invocations=3*c["task_count"]*r,
                             context_runs=3*c["fixture_count"]*r,
                             context_invocations_first=3*c["fixture_count"]*r*(16+3*c["probe_count"]),
                             context_invocations_max=3*c["fixture_count"]*r*(16+6*c["probe_count"])) for r in range(4, 51)])


def analyse(records, prereg, stage="final"):
    if stage not in ("pilot", "s3", "final"):
        raise ValueError("stage must be pilot, s3 or final")
    c = dict(CONSTANTS)
    c.update(prereg)
    for key in ("bootstrap_seed", "within_seed", "exclusion_cap", "preregistered_r", "probe_thresholds", "unedited_content_tokens", "pool_size", "task_count", "fixture_count", "probe_count"):
        if key not in c:
            raise ValueError(f"missing prereg constant: {key}")
    records, flagged, voided = validate(records, prereg)
    cells, groups = defaultdict(list), defaultdict(list)
    for r in records:
        if r["track"] == "B":
            cells[r["task_or_fixture_id"], r["arm"]].append(r)
            groups[r["arm"], r["model_id"]].append(r)
    comparisons = {}
    for a, b in (("K1", "K0"), ("K1", "N"), ("N", "K0"), ("K1f", "K0f"), ("K0f", "K0")):
        if any(arm == a for t, arm in cells) and any(arm == b for t, arm in cells):
            comparisons[f"{a} against {b}"] = task_comparison(cells, a, b, c)
    result = dict(constants=c, flagged_per_batch=flagged, voided_per_batch=voided,
                  descriptive=per_model_descriptive([r for r in records if r["track"] == "B"]),
                  task_comparisons=comparisons, context=context_runs(records, c))
    if stage == "pilot" and "N against K0" in comparisons:
        result["power"] = power_report(cells, comparisons["N against K0"], records, c)  # CR-01: pilot shape only
    if stage == "s3":
        for comparison in comparisons.values():
            for key in ("rule1_pass", "practical_pass"):  # CR-01: no rule is tested at S3
                comparison.pop(key)
    result["open_point"] = 'Gate S2 says "probe thresholds with the 1/P allowance"; this analysis uses the minimum of five unedited scores, with no allowance.'
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("logs", type=Path)
    p.add_argument("prereg", type=Path)
    p.add_argument("--json", type=Path, required=True)
    p.add_argument("--stage", choices=["pilot", "s3", "final"], default="final")
    a = p.parse_args()
    records = []
    for path in sorted(a.logs.glob("*.record.json")):
        records.append(json.loads(path.read_text(encoding="utf-8")))
    result = analyse(records, json.loads(a.prereg.read_text(encoding="utf-8")), a.stage)
    rendered = json.dumps(result, sort_keys=True, indent=2, allow_nan=False)+"\n"
    a.json.write_text(rendered, encoding="utf-8", newline="\n")
    print("# Token-aware analysis\n\n```json\n"+rendered+"```")


if __name__ == "__main__":
    main()

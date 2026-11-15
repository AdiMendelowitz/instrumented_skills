# Analysis script specification (S2 step 2)

Date 2026-10-18 (file dated 2026-10-19 as planned). Author: the lead. Builder: Codex on Adi's machine. Reviewer: a weaker Claude model with the critique skill. Source: design of record `token-aware-m1-m3-plan-2026-10-16.v3.md` (md5 a01020f7947b6eaa24d599a9cb71ca5f), sections 3.2, 3.3, 3.5 and 5.

## Executive summary

`analysis.py` reads the run logs written by the harness and prints one report holding every number the rules need: the paired task-mode test (rule 1), the quality guard (rule 2), the context-audit test (rule 4), the power analysis, the r-sizing formula and the exact interval for the trigger rate. Every statistical routine has a unit test that reproduces a worked value from the design, so a wrong implementation fails before it touches data. Seeds are inputs and are printed. The script has no network access and no hidden defaults: every constant sits in one block at the top and is echoed in the report. Its md5 is frozen in `prereg.md`.

## 1. Files

Under `notes\token-aware\eval\harness\`: `analysis.py`, `test_analysis.py`, `analysis-fixtures\` (synthetic logs). Python 3.12; `numpy` and `scipy` are allowed. The builder runs `pip show` for each package and pins the version shown in `environment-recipe.md` before any reinstall.

## 2. Inputs and data checks

- A directory of per-run JSON records (harness schema, harness spec section 4) and a `prereg.json` holding the constants of section 9.
- Before any statistic: drop runs flagged by the cost assertion, count them, and print the count per batch. Stop with a clear message if any task-and-arm cell has no valid run left, or if flagged runs exceed the cap in `prereg.json`. An empty cell is never scored.
- Check every record's Claude Code version, model ID and harness md5 against `prereg.json`; any mismatch stops the analysis.

## 3. Task mode, primary endpoint (design 3.2)

Per task and arm: cost per success = total API-equivalent cost of the task's runs divided by the number of runs whose check passes; when none pass, the divisor is 0.5. The task value is the natural log of that quantity. The comparison is the paired difference of the log values for a candidate arm and a comparator arm (K1 against K0, K1 against N, and N against K0 for the pilot).

Descriptive output per arm and model: cost over all runs; cost of passing runs only; the four token classes; an uncached-equivalent total (every input token priced at the base input rate); trigger rate; success rate; cache-read share. Cache-adjusted sensitivity: each run's input side repriced with the cache-read share set to the mean share of the two compared arms (total input tokens unchanged); this definition is fixed here and Adi may replace it at Gate S2.

## 4. Rule 1 tests (design 3.2, 3.3, section 5)

On the log differences d_i over the n tasks:

1. Primary: one-sided paired t-test, H0 mean(d) >= 0, alpha 0.025, df n minus 1. Equivalent report: the upper end of the two-sided 95 per cent interval below zero.
2. Exclusion test: the same test without every task where either compared arm has no passing run. Print the excluded task ids.
3. Sentinel test: the same test with divisor 1.0 in place of 0.5 for no-pass cells. Reported, not gating.
4. Practical bar: the point estimate of mean(d) must be at or below ln 0.85, which is minus 0.1625 (print to four decimals; the design quotes minus 0.163).
5. Task-level bootstrap: 10,000 resamples of tasks, seed from `prereg.json`, 95 per cent percentile interval of mean(d); labelled "limited: few distinct resamples".

Rule 1 verdict: PASS only if tests 1, 2 and 4 all pass; test 3 and 5 are printed beside it. The zero-pass sensitivity note (one extra passing run on a no-pass task moves the log difference by about 0.69) is printed with the number of no-pass cells.

## 5. Rule 2, quality guard (design 3.3)

Per task: success proportion of each arm. Paired differences (candidate minus comparator). Task-level two-sided 95 per cent t interval of the mean difference (df n minus 1). The guard holds when the lower end is above minus 0.10 (the margin is an input, default 0.10, confirmed by Adi at Gate S2). Run for K1 against K0 and K1 against N.

## 6. Context-audit mode and rule 4 (design 3.2, 3.3, 3.5, section 5)

- Per run: content tokens of the edited fixture = mean over the run's 5 triples of FILE minus BASE minus WRAP (harness spec section 2). Print the mean and the range.
- Probe score of a run: the share of its probe invocations (P probes times 3 repeats) whose grader passed. A run whose first pass scores below the fixture's threshold gets a second pass; it is scored at the fixture's unedited size only if both passes are below the threshold. The threshold is the minimum of the fixture's 5 unedited scores, with no allowance (sections 3.2 and 3.5 of the design; see the open point in section 10 below). Print the share of runs scored at the unedited size.
- Rule 4 test: Welch one-sided t-test at alpha 0.025 of H0 mean(AS) >= 0.9 times mean(AN), computed on the AS values against the AN values multiplied by 0.9 (Welch degrees of freedom from the two sample variances, the AN variance scaled by 0.9 squared). If both arms have zero variance, the test cannot run and rule 4 is FAIL with the reason. If r is below the preregistered r, rule 4 is FAIL with the reason underpowered.
- ASn: trigger count k of r with the exact (Clopper-Pearson) two-sided 95 per cent interval. Test: 5 of 5 gives 0.48 to 1.00 (two decimals); 0 of 5 gives 0.00 to 0.52.
- F1 results are reported labelled in-sample and never gate.

## 7. Power analysis (design 3.3)

Inputs from the pilot: per-task log differences of N against K0 (6 tasks, 5 runs per arm), per-task success differences, and the CV of the 5 AN content-token values on F2 after rescoring.

1. Upper 80 per cent one-sided bound of a standard deviation s from n_p tasks: s times sqrt(df / chi2.ppf(0.20, df)) with df = n_p minus 1. Unit tests: factor 1.46 at df 5, 1.56 at df 4 (two decimals).
2. Rule 1 task count: smallest n such that a one-sided paired t-test at alpha 0.025 has power 0.80 to detect a mean log difference of minus 0.1625, with the SD set to the upper bound from step 1 (noncentral t, df n minus 1, ncp = 0.1625 times sqrt(n) over SD). Repeats: the script reports, for repeats r in 3, 5, 8, 10, the SD obtained by splitting the pilot SD into a between-task and a within-task part (within-task variance estimated by resampling runs inside each task and arm in the pilot, 2,000 resamples, seed from `prereg.json`; the between part is the remainder, floored at zero; the within part scales with 5 over r), then the n for each r.
3. Rule 2 task count: smallest n such that, when the true success difference is zero, the guard holds with probability 0.80: power = 1 minus nct.cdf(t_crit, n minus 1, ncp) with t_crit = t.ppf(0.975, n minus 1) and ncp = 0.10 times sqrt(n) over the upper-bound SD of the success differences.
4. The larger of the two counts wins. The pool must hold at least twice the held-out count and never fewer than 16 tasks; the script prints a clear message if twice the count exceeds the pool (Adi then chooses at Gate S2 between a larger pool and a larger minimum effect).
5. Rule 4 runs per arm r: with AS at 0.85 times AN and the comparator at 0.9 times AN, standard error of the difference of means = CV times AN times sqrt((0.85 squared plus 0.9 squared) divided by r), CV set to the upper 80 per cent bound (factor 1.56 at df 4) of the pilot AN CV and used for both arms; r is the smallest count at which the noncentral t power for a difference of 0.05 times AN reaches 0.80 at the one-sided 0.025 critical value, with Welch degrees of freedom from the two arm variances. Worked values, which are unit tests (computed with scipy on 18 October): CV 2, 3, 5, 8, 10 per cent give r = 4, 6, 14, 32, 50; at r = 5 the power is 0.98, 0.75, 0.36, 0.17, 0.12. If the implementation disagrees with a worked value, the builder reports the disagreement and both numbers and does not adjust either.
6. Run budget as a function of r for both tracks, in invocations and in runs (harness spec section 2; design section 6): printed as a table for r from 4 to 50.

## 8. Output

One report, Markdown plus a JSON file with the same numbers, holding: constants echoed; data checks; sections 3 to 7 results; every seed. Repeating the run on the same logs and `prereg.json` gives byte-identical output.

## 9. Constants (in `prereg.json`)

Alpha 0.025 one-sided; minimum effect ln 0.85; quality margin 0.10 (Adi confirms); zero-pass divisor 0.5 and sentinel 1.0; AS target 0.85 and comparator 0.9 of AN; detection difference 0.05 of AN; power 0.80; chi-square coverage 0.80; bootstrap resamples 10,000 and seeds; exclusion cap; preregistered r; probe thresholds; unedited content tokens per fixture; pinned versions; harness md5.

## 10. Open point to report, not to resolve

The Gate S2 paragraph of the design (section 6) lists "probe thresholds with the 1/P allowance", while sections 3.2 and 3.5 define the threshold as the lowest of 5 unedited scores and state that no allowance is used. The script follows sections 3.2 and 3.5. The lead raises the difference with Adi at Gate S2.

## 11. Reporting

The builder returns a CODEX REPORT on the console listing each unit test with its pasted result (including every worked value above), the pinned package versions from `pip show`, and the md5 (32 characters) of `analysis.py` and `test_analysis.py`. A count, hash or existence claim appears only with the command output that shows it. No git command, no write under `.claude\`, `ops\sync\`, `_to_delete\` or `skills\`.

# final.md | token-aware M2 final batch | opened 2026-11-09 (S4g)

Design v4 section 6, S4 steps 3 to 5; rules 1, 2 and 4 by analysis.py 1698f8d9 `--stage final`. Every figure is labelled measured or estimate.

## Candidate (S4 step 4)

| arm | folder | tree md5 (after CR-08) | SKILL.md md5 | SKILL.md lines |
|---|---|---|---|---|
| K0 | candidates\4985f959\token-aware | 4985f959aabde25bdf2d08e0614fff1c | 8bb49369cc7dd3c89de1afdf49d6a9ed | 110 |
| K1 | candidates\93263e8f\token-aware | 93263e8f72992caf8379cada56f01e04 | a1430c9a3c4e58522bbf08e008bd1076 | 111 |

Each final tree differs from its CR-07 tree (eda5e150, 0f7bd41b, both kept unchanged as CR-07 evidence) in tools\rates.json only (CR-08 and CR-08-E1, driver checks and shell recipe 2026-11-09). Every harness run must end by 2026-12-09 (cost.py raises after `expires`; warnings from 2026-12-02).

## Rates check (S4 step 3)

2026-11-09: 53 of 53 cells equal, three rows re-fetched by the lead; rates.json 1788fe18, expires 2026-12-09 (CR-08 b).

## P2 (measured 2026-11-09)

PASS: K1 tools tests 117 passed (CONTEXT_PAYLOAD and K1_SKILL_MD set; workspace pytest 9.1.1); SKILL.md 111 lines, under 500.

## P1 (CR-08 a)

PASS (measured; CR-08-E2 approved 2026-11-09 13:11). Batch 20261109T103033-9c51aafa, 30 calls, 0 flags, 0.1397 USD; scored by prepared\p1-run-2026-11-09.v2.py b0c882dc, summary eval\P1-summary-20261109T103033-9c51aafa-v2.json 768377b2 (v1's INCOMPLETE summary kept in eval\logs).

| part | K0 | K1 | reading | bound | CR-08 | as written |
|---|---|---|---|---|---|---|
| description tokens over no skill | 108.0 | 157.0 | K1 minus K0 49.0 | 120 | PASS | FAIL |
| forced-load tokens over the skill-absent call | 3,244.0 | 3,422.0 | ratio 1.0549 | 1.10 | PASS | FAIL |

Sensitivity (reported only): forced ratio 1.0145 against the description no-skill call, 1.0085 on raw totals, 1.0106 on body only. Noise: SD 0 for every K0 and K1 call, 11.9 for the forced no-skill call.

History: first run printed INCOMPLETE because driver v1 voided every forced triple on the no-skill call's attempted Skill call (`triggered` marks an attempt, runlib.py lines 525 to 535), although each such call ran with the skill absent (`Unknown skill: token-aware`). Method, as committed before the run: driver prepared\p1-run-2026-11-09.py 110fe7dfeaa4487cf19d0cc5115691fc (Sonnet draft, Haiku review with 2 findings fixed, lead mutation pass 8 of 8 mutants killed, selftest 15 of 15 in the workspace): one batch of 30 short calls through harness_k1's snapshot checks, 5 description triples (no skill, K0 4985f959 only, K1 93263e8f only; set G absent) and 5 forced-load triples (prompt "Use the token-aware skill. Then reply with the single word OK."); a triple counts only when every call is valid, every forced K0 and K1 call loaded the skill and no other call did (v2: no other call had the skill installed). INCOMPLETE (fewer than 5 valid triples in a part, or a K0 forced delta of 0 or less) gives no verdict and goes to Adi. Bounds: description content tokens K1 minus K0 at most 120; forced-load delta K1 at most 1.10 x K0. Prediction: as written FAIL on both clauses; under CR-08 PASS on both.

## Final batch

Package pinned 2026-11-10 (S4h) and launched the same day (results in the next section). CR-09 approved 2026-11-10 12:48 (prepared\cr-09-change-record-2026-11-10.v2.md 2122907653606700875c4bf506d36bad): track A runs on F2 only and F1 is not run (CR-09), so no F1 figure is reported.

| item | path | md5 |
|---|---|---|
| launcher | prepared\s4final-run-2026-11-10.py | 1939d7b194275b46ed0c83b8d9a2e085 |
| manifest list (13 manifests) | eval\s4\s4final-manifests.md5 | eaa57f5c |
| K0 tree (arms N, K0, K0f) | candidates\4985f959\token-aware | 4985f959aabde25bdf2d08e0614fff1c |
| K1 tree (arms K1, K1f, AN, AS, ASn) | candidates\93263e8f\token-aware | 93263e8f72992caf8379cada56f01e04 |
| live rates.json read by the cost assertion | skills\token-aware\tools\rates.json | 1788fe18 (read 2026-11-10 before the launch and again after the run, unchanged) |

Plan (measured, launcher `--check` on the device shell 2026-11-10: 8 of 8 pins, 13 of 13 manifests and both trees OK): "plan: 13 batches, 600 task runs, 18 track A runs; already done: 0 []". The device shell's Python 3.10 is refused by the launcher's 3.11 check, which does not apply to the venv Python that runs the batch. 12 track B batches (held-out T02, T04, T05, T09, T11, T12, T14, T15, T21, T22, T23, T24; arms N, K0, K1, K0f, K1f; 10 rounds) and one track A batch on F2 (AN, AS, ASn; 6 rounds).

Estimate by script from CR-07 per-run figures: 37.51 USD and 6 h 26 min with F2 only (53.48 USD and 9 h 05 min as written with F1). Every harness run must end by 2026-12-09.

Predictions written before the launch (CR-09, CR-06 v2 rule): rule 1 FAIL (dev estimate -0.070612 against the bar -0.223; probability of a pass 0.025 at the dev effect and 0.083 with the dev estimate's uncertainty, by simulation, an estimate), rule 2 PASS, rule 4 FAIL (power 0.072 at r = 6 with the S3 upper CV 0.180212); M2 DROPPED.

Stop rules (CR-09 c): a usage-limit, network or power stop resumes on the same `--run` line; a version assert, an empty task-and-arm cell or a cost-assertion exclusion is a broken final batch (design section 3.2, R3) and is not resumed. Before analysis a script asserts 600 track B and 18 track A records from the 13 done-marker batch ids (CR-09 d). Known limitation: the pinned seed 20261019 gives every batch the same arm order (mean position K0 1.7, K0f 1.8, K1f 1.8, K1 2.2, N 2.5; AN 0.83, ASn 1.00, AS 1.17).

## Final batch results (run 2026-11-10, analysed the same day)

Run: Adi's window, launcher 1939d7b1, ledger `eval\logs\build\s4final-ledger.txt`. RUN start 2026-11-10T10:53:35Z, RUN complete 2026-11-10T18:05:40Z (7 h 12 min against the 6 h 26 min estimate), 13 of 13 batches exit 0 at the first attempt, no stop and no resume. Track B ended at 13:48:35Z and track A took the remaining 4 h 17 min.

Records (measured on the device, CR-09 d): 1,788 record files from the 13 done-marker batch ids and none from any other batch on that date; 600 track B records in 60 cells of exactly 10 (12 tasks x 5 arms); 18 track A runs with triples (6 each for AN, AS, ASn); no flag of any kind on any record, so 0 cost-assertion exclusions and 0 voids. Claude Code 2.1.303 and claude-sonnet-5-5 on every record. Evidence: `eval\s4\s4final-records-2026-11-10.jsonl` ab1cec51 (the 1,788 records, one per line), `eval\s4\s4final-record-sums-2026-11-10.txt` c79d03e8 (md5 of each record file), `eval\s4\s4final-analysis-2026-11-10.json` b338e428 (analysis.py 1698f8d9 `--stage final` with prereg.json 31322c00, run in the workspace, exit 0). A Haiku agent recomputed the three rule verdicts from that JSON alone and agrees.

Computed cost of the batch: 44.34 USD (track B 16.23, track A 28.11), equal to the reported `total_cost_usd` sum, against the 37.51 USD estimate.

| rule | reading | result | verdict |
|---|---|---|---|
| 1 optimisation | K1 against K0, 12 held-out tasks, 10 runs per arm | mean log difference -0.039017 (ratio 0.9617), 95 per cent interval [-0.092410, 0.014376], one-sided p 0.068; significance test not passed, exclusion test not passed (no task excluded), point estimate above the bar -0.223 | FAIL |
| 2 quality | quality guard, K1 against K0 and K1 against N | every arm passed 120 of 120 runs, so both success differences are 0 on every task and both guards hold | PASS |
| 4 context audit | AS against 0.9 x AN on F2, r = 6 | AN mean 1,902.5 content tokens (SD 69.3), AS mean 1,879.0 (SD 163.5), AS over AN 0.988 against the target 0.85; Welch t 2.335, df 6.43, p 0.972 | FAIL |

Rule 4 power (CR-03): `rule4_from_sizes` on the six final AN sizes gives cv 0.036443 and upper cv 0.053243 (rule4_r 15). `rule4_power(6, 0.036443, alpha=.025, target=.85, comparator=.9)` is 0.687 and `rule4_power(6, 0.053243, ...)` is 0.390. The S3 re-estimate was r = 158 from six sizes that mixed measured and substituted values (run 0123). CR-03 calls a FAIL at this power uninformative as a test; the point estimate itself, a 1.2 per cent reduction, is far from the 15 per cent target.

M2 outcome: rules 1 and 4 FAIL, so the design's success condition for the skill (section 5) is not met. Under ADR-08 and PLAN.md's M2 completion condition the milestone itself is DONE on 2026-11-10, because this file records a verdict for rules 1, 2 and 4 from the single analysed final batch; DROPPED is reserved for removal by a change record. The previous version of this paragraph (final.md c2a82c6e) and CR-09's prediction line used the word DROPPED for this same outcome.

Reported whatever the outcome (design section 5):
- K1 against N (the headline for readers): mean log difference 0.007699 (ratio 1.008), interval [-0.063281, 0.078680]. With K1 installed a task costs the same as with no token skill.
- N against K0: -0.046716 (ratio 0.954), interval [-0.128936, 0.035504].
- K1f against K0f (the guidance effect once the skill loads): 0.047859 (ratio 1.049), interval [-0.030232, 0.125949].
- K0f against K0: 0.276059 (ratio 1.318), interval [0.150127, 0.401991]. A forced load of the skill raised the cost per success by about 32 per cent on these tasks with no change in success.
- Trigger rates, track B: N, K0 and K1 0 of 120 each; K0f and K1f 120 of 120 each. Neither K0 nor K1 loaded itself on any held-out task, so the K1 against K0 difference is the effect of the description alone.
- Track A triggers: AS 6 of 6, ASn 6 of 6 (exact interval [0.541, 1.0]), AN 0 of 6. ASn mean 1,985.5 content tokens (SD 333.0) as scored. One ASn run (0123) failed both probe passes (0.667, 0.667 against the threshold 0.711) and is scored at the unedited size 2,644 where its triples measured 2,184, so the three arm means sum to 460 tokens more than the 18 run means in the analysis JSON; share scored at the unedited size 1 of 18.
- AN itself brought F2 from 2,644 unedited content tokens to a mean of 1,902.5, a 28 per cent cut with no skill installed.
- Sentinel-1.0 sensitivity: identical to the primary means in all five comparisons, since no task has a zero-pass cell. Cache-adjusted sensitivity for K1 against K0: -0.017517, interval [-0.0632, 0.0282].
- Mean cost per run, track B: N 0.02277, K1 0.02349, K0 0.02412, K0f 0.03117, K1f 0.03367 USD; cache-read share 0.93 to 0.96 in every arm.

Predictions against outcome (CR-09): rule 1 FAIL predicted and observed; rule 2 PASS predicted and observed; rule 4 FAIL predicted and observed; the outcome CR-09 called M2 DROPPED (rules 1 and 4 FAIL) predicted and observed. The predicted rule 4 power (0.072 at the S3 CV) was too low: the final AN sizes give 0.390 to 0.687.

Limits of these results: every arm passed every run, so the held-out tasks cannot show a quality difference in either direction and rule 2 passes at a ceiling; the pinned seed gives all batches one arm order (positions in the Final batch section); the bootstrap intervals are labelled by analysis.py as limited (few distinct resamples); analysis.py's open point on the 1/P probe allowance stands (the minimum of five unedited scores is used, with no allowance); F1 was not run (CR-09).

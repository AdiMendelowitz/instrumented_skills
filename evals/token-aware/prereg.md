FROZEN at Gate S2 2026-10-25 (Adi; quoted approvals below). Changes only through `APPROVE change <id>`.

# prereg.md (token-aware M1, Gate S2)

Status: draft opened in S2 step 0 on 2026-10-18 (the S2 session prompt is dated 2026-10-19; the machine date at the time of the work was 2026-10-18). S2a stopped at step 3 on 2026-10-18 because the F1 reproduction of the 11 October figure (5,365 plus or minus 54 content tokens) failed; steps 4 and 5 did not run, so every field marked "not yet set" below stays open. No F1 material is frozen in this file. Updated 2026-10-19 in S2b: F1 attempt 2 and ADR-10 (step 3 section below), the fixed `prove_checks.py`, the revised proofs brief and the amended harness specification (md5 values in the table below). Nothing in this file is approved until Adi approves it at Gate S2.

## K0 files (the skill as frozen at Gate S2; full md5 computed on the device)

| file | md5 | read back |
|---|---|---|
| skills\token-aware\tools\rates.json | 1788fe1848ac62e4ad1800663b1db120 | 2026-11-09, CR-08 renewal (dates only; was 61315848136edad1f2fd15348d4d9462, 2026-10-18); same file in candidates\4985f959 (K0) and candidates\93263e8f (K1), the renewed copies of eda5e150 and 0f7bd41b (CR-08-E1) |
| skills\token-aware\references\pricing.md | ca45820899e92af62fadcb16539fc480 | 2026-10-18, S2 step 0, after commit; read again at close |
| skills\token-aware\SKILL.md | 8bb49369cc7dd3c89de1afdf49d6a9ed | 2026-10-18, S2 step 0 (unchanged); read again at close |
| skills\token-aware\tools\cost.py | e888bff9a87c2e76ca3310b1898d98ce | 2026-10-18, S2 step 0 (unchanged); read again at close |
| skills\token-aware\tools\test_cost.py | 9a83194c0689834917bea8836635a68d | 2026-10-18, S2 step 0 (unchanged); read again at close |

The remaining files of K0 (the other references) get their full md5 values at the freeze.

## Rates (S2 step 0, ADR-07)

- rates.json verified 2026-10-18, expires 2026-11-17 (30 days). The check repeats in the five working days before the final batch, with `expires` at least ten working days past the planned batch end.
- Sources: the pricing, prompt-caching and models-overview pages, tabulated by claude-haiku-5-5 through the Agent tool, then three cells re-fetched by the lead and matched (Haiku 5.5 price rows, Sonnet 5.5 tool overhead and cache-hit multiplier), plus the tokenizer, long-context and geo statements.
- Changes against the table of 2026-09-28: `claude-haiku-5-5` added; Sonnet 5.5 cache-hit multiplier set to 0.05x (it was the 0.1x default); Sonnet 5.5 tool overhead 286 is on the pricing page, so it is no longer labelled ASSUMED; the Fable 5.1 note on line 91 corrected; every provenance date moved to 2026-10-18.
- Known limit: claude-haiku-5-5 is priced by prompt length. The table carries the tier for prompts up to 100,000 tokens (in 0.10, out 0.50). A request over 100,000 prompt tokens pays in 0.50 and out 2.50 and is not modelled, so it fails the 1 per cent cost assertion instead of being mispriced.
- Tests: 96 passed on a copy of `tools\` with the new rates.json, in a scratch venv (pytest 9.1.1, Python 3.13.16).
- RAID I2 and D3 are CLOSED with these md5 values (RAID.md md5 899045569e199020ae68420c96b4e69b at 2026-10-18; RAID.md after S2b: 6271e9f03faed3eaa6f6f5de1bf6c1d7).

## Pool and specifications frozen in S2 steps 1 and 2 (2026-10-18; md5 read back on the device at close)

| item | md5 | note |
|---|---|---|
| notes\token-aware\eval\pool-tree-md5-2026-10-22.txt | e4d00b93d244af6ea191d58d58129af5 | 466 lines, the frozen tree md5 after ADR-20 (option C: F2 and F3 trigger lines anchored, 4 md5s changed); `md5sum -c` gave OK=466 FAILED=0 on 2026-10-22; pre-amendment record: pool-tree-md5-2026-10-19.txt 1a87a8c3f52c40014cba166fe16bb702, kept on the device |
| notes\token-aware\eval\eval-pool-2026-10-22.zip | 7d7915811d9b22583324e603e9ed94ef | archive of the 466 listed files after ADR-20 (content verified against the list); pre-amendment record: eval-pool-2026-10-19.zip d3768067c2b5c1dffeb37aa5a8a30f8c, kept on the device |
| notes\token-aware\eval\pool-tree-md5-2026-10-28.txt | 17883dbbbe0dbfcf7304bf2da0334d32 | 466 lines; T13 task text amended by CR-04; 1 of 466 md5s changed (tasks/T13/task.md 2584e802 to e96028bf); `md5sum -c` gave OK=466 FAILED=0 on the device 2026-10-29 (driver step 4i and the lead's read-back); written 2026-10-29 09:04:57Z UTC under the 2026-10-28 name; pre-amendment record: the 2026-10-22 row above, kept on the device |
| notes\token-aware\eval\eval-pool-2026-10-28.zip | 430ddedf43e8035d82c70aec67ec7d83 | archive of the 466 files of the 2026-10-28 list; T13 task text amended by CR-04; 1 of 466 md5s changed; content verified against the list (OK=466 FAILED=0, evidence prepared\evidence\cr04-20261028T204500Z.txt 3fe2b266); its md5 depends on the archiver's zlib (the Linux bed on Python 3.11 to 3.13 gave ffef8c6a for the same content), so it is pinned from the device; pre-amendment record: the 2026-10-22 row above, kept on the device |
| notes\token-aware\eval\briefs\task-pool-brief-2026-10-19.md | 1d42c97206c614418519e8bde0a5fca8 | brief to the pool writers |
| notes\token-aware\eval\briefs\codex-brief-proofs-2026-10-19.md | 8a9c629ce229a77da83956747e138903 | brief for the independent check proofs; revised 2026-10-19 (S2b): step 3 passes the literal absolute root (was ec979012138a5d6266d85a1edacbf5bd) |
| notes\token-aware\eval\briefs\codex-brief-build-2026-10-19.md | 2e4b33c7bf78f54324b6ed5bab1455d2 | Codex build brief for the harness and the analysis script (RAID D1b), 2026-10-19 (S2b); interpreter Python 3.13.14 in cmd (Adi, 2026-10-19), a deviation from the 3.12 of both specifications; critiqued in two rounds by a fresh reviewer (12 findings, then 2, all applied) |
| notes\token-aware\eval\harness\harness-spec-2026-10-19.md | ece72d475edc3c1dc927e8b032a69fd3 | specification for the harness; section 6 amended 2026-10-19 (S2b, ADR-10): dose-response check and F2 repeatability replace the two-character WRAP check, fixed config and working directory paths (was 63803c28c26d9468bad53a97530541a6) |
| notes\token-aware\eval\harness\analysis-spec-2026-10-19.md | c3ff9a6d94e40611c94c14d748d85bf5 | specification for the analysis script |
| notes\token-aware\eval\harness\prove_checks.py | 87acc85df0f079e6a82977ef0434b72b | runs every check and grader on its pass and fail states; fixed 2026-10-19 (S2b): resolves the root, exits 2 with an ERROR line on a missing root or zero items (was d88f22cbd03894f4a5676d028c781acf) |

- Composition: the tree holds 460 files under `tasks`, `fixtures` and `probes` plus 6 manifest files (command output of 2026-10-18), matching the design of the task-pool brief: 24 tasks (T01 to T24), set G of 15 stub skills, fixtures F2 and F3, and 15 probes for each of F2 and F3. The tree held 0 `__pycache__` folders at close.
- Proof status: the lead ran `prove_checks.py` in the workspace on the tree before freezing and recorded 54 OK of 54 (24 task checks and 30 probe graders). That run is the lead's own and does not count as the independent proof. Independent proof by Codex (RAID D1c), 2026-10-18 on Adi's machine, Python 3.13.14 in cmd (the brief named 3.12, which exists only in the PyCharm venv; deviation labelled): with the literal absolute root, `RESULT: 54 OK of 54; 0 BAD`; the earlier runs with `.` (0 OK of 54, exit 2 each) and with `"%CD%"` (0 OK of 0) failed on the runner's relative-root defect, not on any check. Re-proof after the fix, 2026-10-19 (S2b, workspace, clean copy of the tree, tree md5 file gave OK=466 before and after): `RESULT: 54 OK of 54; 0 BAD` from `.` and from the absolute root on Python 3.13.16 and on Python 3.12.3, item lines identical between the two roots; an empty root and a missing root each exit 2 with an ERROR line. The checks, graders and tree are unchanged, so the Codex proof stands. Not run: the literal Windows command of brief step 3 in cmd with the fixed script. Interpreter floor, found 2026-10-19 (S2b) on the device's Linux shell (Python 3.10.12): 51 OK of 54, with T20 and F3/P05 failing on `import tomllib` and T15 on `datetime.fromisoformat` of timestamps ending in `Z`, both available only from Python 3.11; the same tree gives 54 OK of 54 on Python 3.11 in the workspace. Every proof and run therefore needs Python 3.11 or later; the build interpreter is Python 3.13.14 (Adi, 2026-10-19, answer quoted: "cmd python 3.13.14"). Lead's note, 2026-10-19: the false-FAIL rate of harness-spec 6.1 items 2 and 3 under a sound harness at SD 45 is 3.0 per cent by simulation (`notes\token-aware\prepared\dose-false-alarm-2026-10-19.py`, md5 e25d7118cfe29f7083f0feff73ff509b); the spec's "expected SE of a dose mean about 20" is the SE of a dose mean, while item 3 tests its residual (SE 11.0 to 16.8). A check or grader without a non-zero exit on its fail state goes back to its writer and the tree is re-frozen with a new md5.
- Harness and analysis scripts: the two specifications are frozen above. Codex built the scripts and their tests to the lead's brief (ADR-11 to ADR-13, 2026-10-19); superseded 2026-10-23: the md5s, the recipe, the npm pin and the 6.1 result are in the S2g section below (the WRAP check was replaced by ADR-10).

## Harness and analysis scripts frozen in S2g (2026-10-23; md5 read back on the device after the two pinned patches)

Built by Codex to the lead's brief from the frozen specifications (ADR-11 to ADR-13; RAID D1b CLOSED 2026-10-23) and amended by lead-written, Codex-applied patches, `prepared\s2g-harness-patch.py` (904480d8e81126b50f69407a7766dd8c; critique F1 to F4, F6 to F8) and `prepared\s2g-bundle-patch.py` (fc47502e532789b917a75ea8a66ea40d; ADR-16 amendment 2, ADR-18 amendments 1 and 2, ADR-21, ADR-10 amendment 3), each applied once by Codex with pytest after (100, then 102 passed). Every run record carries harness_md5, runlib_md5 and pricing_md5; the analysis rejects a record whose three values differ from these.

| item | md5 | note |
|---|---|---|
| notes\token-aware\eval\harness\harness.py | 3e896ad21cf33a4c79199d5ca16f966c | S2g state; S2e-S2f batches carry 3e7d6d7fc1a4fab873bdaa6a939a44a4 |
| notes\token-aware\eval\harness\runlib.py | ce4c6cac89549a1018de1a8d3945179d | S2g state; S2e-S2f batches carry 185e69004fb466af15980fd7f7113fb0 |
| notes\token-aware\eval\harness\pricing.py | 1b03ec48a32b857218a9280e819428d1 | unchanged since the cache TTL ruling (2026-10-19) |
| notes\token-aware\eval\harness\analysis.py | 1698f8d9c56c139b16c7be19e298d849 | CR-01 applied 2026-10-28 (driver evidence cr01-20261028T142913Z.txt and cr01-20261028T164155Z.txt): analyse(stage), rule4_from_sizes, K1f against K0f, F1 skipped; before CR-01 94ac2575d1276c1e0efb0c81092d6976 (kept as prepared\analysis.94ac2575.py), voids excluded, three md5 pins, blended cache-write rate |
| notes\token-aware\eval\harness\test_analysis_cr01.py | 04e8ebfa8e7fba02c7338f23d15b36b3 | CR-01 item 3: 9 tests, 3 must-not-match; copied from prepared\cr-01-test_analysis_cr01.py by the driver |
| notes\token-aware\eval\harness\test_harness.py | 8799f18122032d9804ae9f2cd65407c8 | 102 tests with test_analysis.py on 2026-10-23 |
| notes\token-aware\eval\harness\test_analysis.py | 381592dc6dd3f3cd63234ae05c1d88c6 | fixtures carry write_5m and write_1h, no `write` key; CR-01 erratum (iv), Adi 2026-10-28 18:40 "i approve": lines 104, 105 and 131 call analyse(records,c,stage="pilot"); before the erratum a6b65bfc3e038391e545c2ace7d84deb (kept as eval\harness\test_analysis.py.bak-2026-10-28) |
| notes\token-aware\eval\harness\conftest.py | ff75a46849b019a5e32ad805b475e02f | unchanged |
| notes\token-aware\eval\harness\config.example.json | 2194f8d622f8ee295f1c56ec4814f938 | unchanged |
| notes\token-aware\eval\harness\samples\dose-block.txt | 9412b8d69e37a4dcf3ea74b8d2b0d433 | 1431 B, not doubled; 6.1 PASS at attempt 0 (batch 20261022T101112-3f472f1e: b 460, a -1) |
| notes\token-aware\eval\harness\environment-recipe.md | bec442d71155a868f7aa55b5d846be7d | regenerated 2026-10-23 (A46): manifest, ADR-15 to ADR-21, live-run and Codex launch lines |
| notes\token-aware\prepared\a52v2-classifier.v3.py | fde12669b170f6f68e61ca106d54ffea | I4 verdict tool for S2e-S2f batches (33 self-tests) |
| notes\token-aware\prepared\a52v2-classifier.v4.py | 048482429f953caa9bdbbed420d12ee5 | verdict tool for S2g batches (40 self-tests; flag rule by harness state) |

Decisions recorded since the freeze of 2026-10-18 that bind the harness (full text in `notes\project\DECISIONS.md`): ADR-14 (`syncClaudeAiSkills` false), ADR-15 (`disableBundledSkills` true, `skillOverrides {doctor: off}`, expected residual set {design, plugin-authoring}), ADR-16 (one-year OAuth token in the child environment; amendment 2: no credentials copy in ccfg), ADR-17 (NON_SECRET_FIELDS = {claudeAiOauth.rateLimitTier}), ADR-18 (live runs started by Adi, Codex launch refused; amendment 1: an IN denial voids and stops at once, A48 retired; amendment 2: an OUT Glob or Grep denial is recorded, not voiding), ADR-19 (I4 closing rule A52 v2), ADR-20 (option C, the 2026-10-22 pool), ADR-21 (`launcher` and `config_files` record fields), ADR-10 amendment 3 (`event_counts`, `multi_request_triple`). Harness-spec item 7 as amended by ADR-16 and ADR-17: the exact-string needles are every string of 8 characters or more in `credentials_file` and the token file, literal and JSON-escaped; a needle whose every label names a field in NON_SECRET_FIELDS is dropped; the tier name joins the scrub check before publication; strings found in a credentials file written into ccfg during a run join the needles (ADR-16 amendment 2).

## Step 3, F1 reproduction (2026-10-18 and 2026-10-19)

FAILED twice, then reclassified by ADR-10 (ACCEPTED, Adi, 2026-10-19: "yes"). The tolerance (5,365 plus or minus 54, so 5,311 to 5,419) is unchanged and nothing from F1 is committed (no recipe, no probe set, no md5).

- Attempt 1, 2026-10-18, Claude Code 2.1.302, `context.md` copy of 1,826 B (70 B longer than the record): content 5554, 5494, 5536, 5473, 5454; mean 5502.2, SD 42.0; 0 of 5 inside; gap 137.2.
- Attempt 2, 2026-10-19, Claude Code 2.1.303, all inputs byte-identical to the 11 October record (`ops\sync\pre-edit\CLAUDE.md.2026-10-11` 7,922 B fc57b8340d499a5d1d15fa3fb703eb2e; `ops\sync\pre-edit\decisions.md.2026-10-11-a23` 4,959 B 954aeebc51c097469e1b06eb3928245d; `ops\token-aware\eval-private\f1-inputs\context.md.2026-10-11-original` 1,756 B cb9be5084621506e3e1455af6725214c); five same-batch triples, order seed 20261019, model claude-sonnet-5-5, all 15 calls OK with claude-haiku-5-5 beside claude-sonnet-5-5 in modelUsage: content 5470, 5501, 5594, 5496, 5492; mean 5510.6, SD 48.1; 0 of 5 inside; gap to 5,365 145.6 tokens (6.8 standard errors). FILE minus BASE mean 5684.4 (SD 26.7; attempt 1 5698.4, SD 43.9; 11 October gross 5480). WRAP mean 173.8 (SD 69.5; attempt 1 196.2, SD 65.1).
- Reading: between the attempts FILE minus BASE moved by minus 14.0 (SE 23.0) and content by plus 8.4 (SE 28.6), with the Claude Code version also changing, so at n=5 a 25-token effect from the 70 bytes cannot be resolved either way. The data support only that the 70 bytes cannot close a gap of 145.6; their contribution is unresolved. Cause of the gap: unknown (untested: the Claude Code version, hypothesis H1 on varying config-directory names, changes in how imports are counted). Full record: Project doc `claude/f1-rerun-2026-10-19.md`.
- ADR-10: F1 is a descriptive, in-sample external figure labelled "reproduction failed twice with byte-identical inputs"; the step 3 stop condition is replaced by the harness-spec section 6.1 dose-response check and the section 6.2 F2 repeatability check (54-token tolerance); no F1 result gates rules 1, 2 or 4.

## Gate S2 values (frozen 2026-10-25)

Approvals quoted (Asia/Jerusalem): option D "D" (2026-10-25 11:02); quality margin "confirm" (11:07); model list "approve" (11:09); threshold wording "yes." (11:40); ADR-22, run budget, BRIEF target, split and deferrals "yes" (11:48). The approval of this file and its md5 is recorded in DECISIONS.md ADR-23 and prereg.md5.

- models: claude-sonnet-5-5 only (gating; fixed by harness.load_config through model_id).
- minimum effect: ln 0.80 = minus 0.2231 (option D; was ln 0.85 in design v3; design section 6 step 5 lets Adi choose a larger minimum effect when the pool is too small).
- quality margin: 0.10.
- repeats: 10 per task and arm. Task count: 12 held-out, 12 dev (pool 24; split seed 20261025; the 6 pilot tasks drawn with seed 20261024 are in dev). Power at these values (s2h-judge.v6 sensitivity, 7e78a6ad): 0.952 if the between-task variance is 0, 0.827 at 0.01.
- N against K0 stands in for K1 against K0 in the power analysis (stated assumption). Pilot (batches 20261024T134447-aa65781f, 60 track B runs, all succeeded, success differences 0; and 20261024T151743-09408da9, 5 AN runs on F2; s2h-judge.v6 power, 7e78a6ad): within-task variance 0.035081, between-task variance 0.000000.
- rule 4 runs per arm r = 6, from the pilot CV 0.018272 of the 5 AN runs on F2 (upper 80 per cent bound 0.028460).
- CR-03 (Adi, 2026-10-28 19:00, "APPROVE change CR-03"): r = 6 kept as pre-registered, no pinned value changes. At the final batch the lead reports, beside rule 4's verdict in final.md, the observed power at r = 6 computed with analysis.py's `rule4_power` from the final batch's AN sizes (the call and its inputs quoted; no code change), and the S3 re-estimate r = 158 (CR-01 item 4) as the powered count the approved budget did not allow, with CR-01's caveat that the six S3 sizes mix measured and substituted values (run 0123). A rule 4 FAIL at this power is uninformative; a PASS keeps its alpha of 0.025.
- probe thresholds (the lowest of 5 unedited scores, no allowance; design sections 3.2 and 3.5): F2 0.711111 (scores 32, 33, 35, 34, 33 of 45), F3 0.977778 (45, 44, 45, 44, 45 of 45). analysis.py line 347 still prints the superseded 1/P open point; it is resolved by Adi's ruling of 2026-10-25 11:40.
- unedited content tokens: F2 2644, F3 2619 (5 same-batch triples each, 2026-10-24).
- harness-spec 6.2: PASS 2026-10-24 (means 2644.0 and 2644.0, difference 0.0, tolerance 54).
- broken-rule checks (design section 6 step 5; both passes must fall below the threshold):
  - BROKEN-RULE F2-BR threshold=0.711111 scores=[0.6666666666666666, 0.6666666666666666] VERDICT PASS (P09 sentence deleted; batches 20261025T095228-5afdc98b and 20261025T100504-a7f31124; 30 of 45 both passes; driver evidence 17759c12; folders archived to eval\broken-rule-2026-10-24\, pool list 466 of 466 match)
  - BROKEN-RULE F3-BR threshold=0.977778 scores=[0.9333333333333333, 0.9333333333333333] VERDICT PASS (P03 sentence deleted; batches 20261025T101912-eae9d1d2 and 20261025T102915-c696478d; 42 of 45 both passes)
- usage fields that define content tokens: input_tokens + cache_creation_input_tokens + cache_read_input_tokens (runlib.tokens excludes output_tokens).
- cap on runs excluded by the cost assertion: 0 per batch (config cost_assertion_cap 0; one failed assertion stops the batch).
- void limits (RAID I5): more than 1 of 3 repeats of one probe voided, or more than 5 per cent of a batch voided, makes the batch invalid.
- load-cost ceiling (precondition P1): K1's forced-load usage delta is at most K0's, measured in the same P1 batch.
- live configuration import count, F1 measurements and F1's broken-rule check: measured in S3, descriptive only (ADR-10; Adi 2026-10-25 11:48); md5 only of F1 and its probe set recorded then.
- run budget: 2640 task runs and 84 track A runs; 7764 to 11544 invocations; 194.34 USD at the pilot means of 0.020926 USD per task run and 1.65584 USD per track A run (s2h-judge.v6 budget).
- seeds: analysis bootstrap_seed 20261025 and within_seed 20261024 in prereg.json reuse the split seed and the pilot draw seed.
- analysis scope (independent check 2026-10-25): analysis.analyse calls power_report whenever N and K0 are both present, and power_report accepts only the pilot shape (6 tasks, 5 runs per task and arm, 5 F2 AN runs), so analyse raises on S3 and final-batch records; analyse has no K1f against K0f or K0f against K0 comparison; context_runs raises on any F1 record (F1 has no threshold here; F1 logs go to ops\token-aware\eval-private\ per design section 6); void_cap and expected_cells are absent from prereg.json. S3 baseline figures are computed by a later s2h-judge version, pinned and self-tested before the S3 judge pass (v6 has no S3 subcommand), calling the md5-checked analysis.py functions describe, task_comparison and context_runs, and the I5 void limits are checked by classifier v4 and the judge. A fix to analysis.py for the final batch, with the K1f against K0f pair, goes through `APPROVE change <id>` before M2. Stale since CR-01 (2026-10-28): analysis.py 1698f8d9 analyse(stage="final") covers K1 against K0, K1 against N and K1f against K0f without power_report (line 56); the final batch uses it unchanged.
- T13 amendment (CR-04, approved 2026-10-28 19:05, applied 2026-10-29 09:04:57Z UTC by prepared\cr-04-driver-2026-10-28.py f9558489, evidence prepared\evidence\cr04-20261028T204500Z.txt 3fe2b266, OVERALL OK; pool list pool-tree-md5-2026-10-28.txt 17883dbb): tasks\T13\task.md 2584e802 to e96028bf gains the route-line format sentence; check.py 8f7b7308 unchanged; `prove_checks.py --only T13` gave `RESULT: 1 OK of 1; 0 BAD`. T13's 30 S3 records (0 successes, eval\baseline.md) stay as measured and count in the S3 baseline as recorded; T13 is excluded from every S3-to-S4 comparison, since its S3 figure measures the old text; the S4 dev measure for T13 starts from the first S4 batch started after the boundary; the final batch runs every arm on the amended text. Run records carry no task md5 (runlib.py stamps harness, runlib and pricing md5s only), so a T13 record from any batch started before 2026-10-29T09:04:57Z is old-text. T13 is a dev task (s3\split-2026-10-25.json c87fb9db); no held-out task changed.
- S4 decision rules: CR-05 readings 1 to 7 (prepared\cr-05-change-record-2026-10-29.md baa0e87a, approved 2026-10-29 15:01 before any S4 record was read); judge s2h-judge.v9.py d50e35f6 `s4`, extract s2h-extract.v4.py ac5e69e1; pre-iteration run 2026-10-29 (launcher s4pre-run-2026-10-29.py 45b7ebdf, manifests eval\s4\s4pre-manifests.md5 0d224fa4): S4 VALID, 240 track B and 6 AS runs, 0 voided; verdict STARTING-CANDIDATE (mean log difference -0.025318, successes 115/120 both arms); AS on F3 mean size 1336.833 (reference for iteration 1); output eval\s4\s4pre-judge-2026-10-29.txt 0ccd735f.
- CR-06 v2 (approved 2026-11-08 14:56): reading 5 margin 0.10 on the fixed reference 1336.833, reading 8 trigger gate 0.25 of reading-2 runs in 3 dev tasks (at least 4 runs per task), fallback re-run once then BROKEN-RULE, prediction before build (prepared\cr-06-change-record-2026-11-02.v2.md).
- CR-07 (approved 2026-11-08 17:40; CR-06 confirmed 2026-11-09 09:09): one four-arm batch, K0 eda5e150 paired within batch against K1 0f7bd41b, K3a 9ed3f957, K3b 6f872d71; readings 2, 5 and 8 per arm against its in-batch K0; winner, futility and drift lines; judge s2h-judge.v14.py s4batch (prepared\cr-07-change-record-2026-11-08.v2.md).
- CR-08 (approved 2026-11-09 11:55): P1 bounds for K1, rates.json renewed to expires 2026-12-09, line 102 erratum (prepared\cr-08-change-record-2026-11-09.md); CR-08-E1 (approved 2026-11-09 12:08): final-batch snapshots K0 4985f959, K1 93263e8f; eda5e150 and 0f7bd41b restored to their CR-07 trees
- CR-09 (approved 2026-11-10 12:48): final-batch track A on F2 only, F1 not run, stop rules (prepared\cr-09-change-record-2026-11-10.v2.md)
- arms K0f and K1f run through harness_farms.py (ADR-22; its docstring still says "ADR-22 PROPOSED", left unchanged to keep its md5); every record keeps harness_md5 3e896ad21cf33a4c79199d5ca16f966c and runlib_md5 ce4c6cac89549a1018de1a8d3945179d.

## Artefacts frozen at Gate S2 (md5 computed before commit, read back on the device after)

| item | md5 | note |
|---|---|---|
| notes\token-aware\plans\token-aware-m1-m3-plan-2026-10-16.v4.md | 07604dc8c2eb024b012b4f94c0ba7064 | design of record frozen at Gate S2 |
| notes\token-aware\eval\harness\harness_farms.py | 4e5e873dc934a218eda38118c6f0d2df | ADR-22 wrapper for K0f and K1f; harness.py and runlib.py unchanged |
| notes\token-aware\eval\harness\config.s2h.json | 36a71faca3eb3f1ef0b20226b64ce4e1 | config.example.json 2194f8d6 plus probe_thresholds F2 and F3 |
| notes\token-aware\prepared\s2h-extract.v3.py | 0ca635ab34b6b92c6a3539358621bf93 | log extract, read-only; the pair that produced eval\baseline.md (CR-01 applies (d) corrected this row from s2h-extract.v2 f77acb1a on 2026-10-28) |
| notes\token-aware\prepared\s2h-judge.v7.py | adcafe23c477beeb9045846ae26d6094 | historic pair with s2h-extract.v3 that produced eval\baseline.md (CR-01 applies (d) corrected this row from s2h-judge.v6 7e78a6ad on 2026-10-28); pins analysis.py 94ac2575 |
| notes\token-aware\prepared\s2h-judge.v8.py | faa690a1a797b0c6ae861d581633f36a | current judge (CR-01 applies (d2), 2026-10-28): analysis md5 read from this pin table at run time; s3 verdict removal owned by analyse(stage="s3"); nested pass_test keys not printed at S3 |
| notes\token-aware\eval\harness\harness_k1.py | 9419caa4e348d56e153659ab603134b2 | CR-01 applies (f), ADR-24 (2), 2026-10-28: snapshot wrapper over harness_farms.py; selftest run by Codex: OK in cr01-20261028T164155Z.txt (9419caa4 after the Git Bash md5sum fix; ea204cad, kept as harness_k1.py.bak-ea204cad, failed case f in cr01-20261028T142913Z.txt); copied by the verification driver |
| notes\token-aware\prepared\s2h-broken-rule-driver.v2.py | d6f3bf82c80995c18c380956959c52b8 | builds and archives the broken-rule fixtures |
| notes\token-aware\eval\s2h-pilot-B.json | bd9620e2b347ead975b57ba58ed1a4b8 | pilot track B manifest |
| notes\token-aware\eval\s2h-pilot-AN-F2.json | 632be975bfd625c2adbb9da6032b87e3 | pilot AN manifest |
| notes\token-aware\eval\s3\split-2026-10-25.json | c87fb9db2a3772886cb0904a5503219c | dev and held-out split |
| notes\token-aware\eval\s3\s3-AN-F2.json | f462a78d889353a1cc7bbaf7f29cfe75 | S3 baseline manifest |
| notes\token-aware\eval\s3\s3-B-T01.json | 9993d571640203d7e06140b80b694930 | S3 baseline manifest |
| notes\token-aware\eval\s3\s3-B-T03.json | 7de832a84a6cc6fa94cdb407341715c9 | S3 baseline manifest |
| notes\token-aware\eval\s3\s3-B-T06.json | e6282c5085776d4627a30364648ce027 | S3 baseline manifest |
| notes\token-aware\eval\s3\s3-B-T07.json | e0bea4943f10de2cde7cf8496a84abc4 | S3 baseline manifest |
| notes\token-aware\eval\s3\s3-B-T08.json | 4c9d1ee37b725ed63e9aed5f20cf56a5 | S3 baseline manifest |
| notes\token-aware\eval\s3\s3-B-T10.json | bbc50fa228f3d0eb23584d18086fedf4 | S3 baseline manifest |
| notes\token-aware\eval\s3\s3-B-T13.json | d6174ed98b12a36671af06cc47796526 | S3 baseline manifest |
| notes\token-aware\eval\s3\s3-B-T16.json | bfb7c16b9df0b8bd235b41f28db6e387 | S3 baseline manifest |
| notes\token-aware\eval\s3\s3-B-T17.json | cf1a4c4076d60567f240501f2d16537e | S3 baseline manifest |
| notes\token-aware\eval\s3\s3-B-T18.json | 6242c05944e2c2daf12a48e186009d77 | S3 baseline manifest |
| notes\token-aware\eval\s3\s3-B-T19.json | d7ebbedbcb17c30d1a20f2c80ec10e70 | S3 baseline manifest |
| notes\token-aware\eval\s3\s3-B-T20.json | b949e12197b99092926fa9c714d19cfb | S3 baseline manifest |

## CR-01 applied (2026-10-28, S4b)

Application run cr01-20261028T142913Z.txt (driver b1e14800): patch applied (analysis.py 94ac2575 to 1698f8d9), copies made, OVERALL FAIL on steps i and iii for two causes fixed by CR-01 erratum (iv) and the harness_k1.py case f fix. Verification run cr01-20261028T164155Z.txt (driver cr-01-verify-2026-10-28.py 5c79d88c, md5 53b35459): OVERALL OK WITH ENVIRONMENT LIMIT, END exit_code 0; harness_k1 selftest OK, judge v8 22 of 22 and 29 of 29, test_analysis.py with test_analysis_cr01.py 31 passed, the 21 context-audit tests 20 passed against K1 0f7bd41b with test 6 failing only at symlink creation (WinError 1314; its ".." half passed; the symlink escape is untested on this machine), 21 failed against K0 eda5e150 (negative control), prove_checks T13 1 OK of 1.

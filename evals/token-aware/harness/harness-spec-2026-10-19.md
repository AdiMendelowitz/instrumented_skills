# Harness specification (S2 step 2)

Date 2026-10-18 (file dated 2026-10-19 as planned). Author: the lead. Builder: Codex on Adi's machine. Reviewer: a weaker Claude model with the critique skill. Source: design of record `notes\token-aware\plans\token-aware-m1-m3-plan-2026-10-16.v3.md` (md5 a01020f7947b6eaa24d599a9cb71ca5f), sections 3.1, 3.2, 3.4, 3.5 and 6; measurement method of `plans/claudemd-500-token-plan-2026-10-11.v2.md` Phase A.

## Executive summary

The harness runs Claude Code in headless mode under controlled conditions and writes one JSON log per invocation. It serves two tracks: track B (task attempts with a pass or fail check) and track A (configuration fixtures: an edit run, 5 same-batch token triples on the edited fixture, and probe passes). The acceptance list in section 3 has nine items plus a dry run (item 10); the builder proves each with a test or a recorded dry run and reports the results in a CODEX REPORT. Nothing here fixes a Claude Code flag name from memory: every command line is confirmed against `claude --help` and the first-party documentation by the builder first (item 1 of the acceptance list), and a mismatch is reported, not worked around.

## 1. Files to build

All under `notes\token-aware\eval\harness\` on Adi's machine, Python 3.12, standard library only for the harness itself (`pytest` is allowed for its tests, in a venv outside the synced tree). No git commands. Nothing is written under `.claude\`.

| file | purpose |
|---|---|
| `harness.py` | command line: `run-task`, `run-edit`, `triples`, `probes`, `batch`, `dry-run`, `selftest` |
| `runlib.py` | config-dir builder, `claude` invocation, stream-json parser, credential check, cleanup, hashing |
| `pricing.py` | thin adapter: `from cost import load_rates` (path to the master `skills\token-aware\tools\` taken from a setting), cost assertion |
| `test_harness.py` | unit tests, one group per acceptance item, with recorded sample events under `harness\samples\` |
| `environment-recipe.md` | pinned versions and exact commands; its md5 is frozen in `prereg.md` |
| `config.example.json` | settings: paths, pin, seed, model IDs, caps (no credentials) |

## 2. Run model

An invocation is one `claude` call. A run is the arm-level unit (design section 6): in track B one invocation; in track A one edit invocation, then 5 triples (3 invocations each: BASE, ONECHAR, FILE), then 3P probe invocations (P probes times 3 repeats), plus a second probe pass when the first scores below the threshold.

Per invocation the harness:

1. Creates a fresh config directory and a fresh working directory under a temporary root outside any synced folder.
2. Installs into the config directory exactly the arm's expected skill set (section 3, item 3) and, for track A, the fixture's instruction file and imports, in the layout Claude Code reads (the builder confirms the layout from the documentation and one dry run; the 11 October method placed `CLAUDE.md` and `memory\` in the config directory).
3. Copies the credentials file into the config directory (Max sign-in needs it there).
4. Runs `claude` headless with `--output-format stream-json --verbose`, the pinned model ID, the prompt, and `CLAUDE_CONFIG_DIR` pointing at the per-run directory. Permission flags are chosen by the builder from the help output so that file edits and shell commands inside the working directory are allowed and nothing else; the choice is written into the recipe.
5. Saves the raw stream to the log directory, parses it, writes the per-run JSON record, runs the check (track B) or the grader (probes), then deletes the config directory and the working directory (item 8).

Measurement of content tokens follows the 11 October method: tokens of one call = `input_tokens + cache_creation_input_tokens + cache_read_input_tokens` from the final `result` event; BASE is the call with an empty instruction file set, ONECHAR the call with a file holding the two bytes `x` and a newline, FILE the call with the fixture. WRAP = ONECHAR minus BASE minus 1; content = FILE minus BASE minus WRAP. The three calls of a triple run back to back in one batch, in a randomised order recorded in the log (block randomisation, item 6). The usage fields that define content tokens are written to the log schema and to `prereg.md`.

## 3. Acceptance list (each item is proved; the CODEX REPORT quotes the proof)

1. **Version pin and assert.** The npm package `@anthropic-ai/claude-code` is installed at one fixed version with automatic updates switched off (the builder finds the switch in the documentation and records it). Before the first run of a batch, and at the start of every run, the harness runs `claude --version` and aborts on any difference from the pin in `config.example.json`. Every run also asserts the full model ID from the `init` event or `modelUsage` equals the configured ID (`claude-sonnet-5-5` for the gating model). Test: a stub `claude` that prints another version makes `run-task` exit non-zero without calling the model.
2. **Per-run `CLAUDE_CONFIG_DIR`.** Each run has its own directory containing the credentials file plus exactly that arm's expected skills and, for track A, the fixture; no plugins, no other settings. A hash of the directory excluding the credentials file (sorted relative paths and file bytes) is logged. Test: two runs of the same arm give the same hash; a stray extra file changes it.
3. **`init` skill list assert.** The `init` event of the stream lists the loaded skills. The run aborts if the set differs from the arm's expected set: N has the 15 stubs of set G; K0 and K1 have set G plus the token-aware skill; AN has the fixture's stubs; AS and ASn have the fixture's stubs plus the skill. Test: with a recorded `init` sample that has one extra skill the run aborts and logs the difference.
4. **`result` usage fields.** The final `result` event provides the usage fields, `total_cost_usd`, `modelUsage` per model, turn count and duration. Tests parse recorded samples (one per model mix, including a run whose `modelUsage` has two models) and fail on a missing field instead of defaulting to zero.
5. **Trigger flag.** A run counts as triggered when the stream holds a tool-use event that loads the skill under test (the builder identifies the event shape from a dry run and records it). Test: a sample with the event gives true, a sample without gives false.
6. **Block randomisation log.** Each round runs every arm of a task once, in an order drawn from a seeded generator (seed in the log). The log records, per run, the gap since the previous run of the same arm and the cache-read share (`cache_read_input_tokens` over the sum of the three input fields). Test: the same seed reproduces the order.
7. **Credential exact-string check.** At run end the harness reads the credentials file, takes every non-empty line of at least 8 characters, and asserts that no log, transcript or record written for the run contains it. A hit fails the run and is logged without printing the string. Test: a planted line in a log makes the run fail.
8. **Config-dir and working-dir deletion and absence assert.** Both directories are deleted at run end and the harness asserts neither path exists, logging the assertion. Test: a locked file makes the run fail loudly rather than pass silently.
9. **Pricing imports `load_rates` from `cost.py`.** `pricing.py` imports `load_rates` from the master `cost.py` and contains no second reader of `rates.json`. The cost assertion prices each model in `modelUsage` with the loaded table and compares the sum with `total_cost_usd`: a difference above 1 per cent flags the run, removes it from every endpoint and counts it. If a task-and-arm cell has no valid run left, or flagged runs exceed the cap in `prereg.md`, the batch stops. Test: a grep of the harness for `rates.json` finds only the path setting passed to `load_rates`; a recorded sample with a price mismatch is flagged; `UnknownModel` and `RatesExpired` stop the batch with their messages.
10. **Dry run.** One complete dry run of the harness (one task-mode run and one track-A run on a fixture with `--model claude-sonnet-5-5`) before the pilot, with every item above checked on its output and the log schema listed.

## 4. Log schema

One JSON object per invocation, one file per run record, plus the raw stream. Fields: run id; track; batch id; task or fixture id; arm; model ID; Claude Code version; harness md5; seed; round and position; start time; gap since the previous run of the same arm; config-dir hash; expected and observed skill lists; the four usage fields; `total_cost_usd`; `modelUsage`; computed cost per model and total; cost assertion difference; trigger flag; turn count; duration; check or grader exit code and reason; deletion assertions; credential check result; flags. Track A records add: the three triple values, WRAP, content tokens, probe results (per probe, per repeat), first-pass and second-pass scores, and whether the run is scored at the unedited size.

## 5. Checkpoints and logs

After every 500 invocations and at session close the harness packs new logs into `tar.gz` parts of at most 30 MB and prints the run tally and the environment recipe. The lead commits them (at most 50 files per call). Track B, F2 and F3 logs go to `notes\token-aware\eval\logs\`; F1 and live-configuration logs go to `ops\token-aware\eval-private\logs\`. A log path outside these two is an error.

## 6. Environment recipe and measurement checks

`environment-recipe.md` records: Node and npm versions, the pinned Claude Code version and the command that installed it, the switch that turns automatic updates off, Python version, the venv and its package versions (run `pip show` for each package and pin the version shown before any reinstall), the permission flags chosen, and the md5 of `harness.py`, `runlib.py`, `pricing.py` and `test_harness.py`.

### 6.1 Dose-response check (replaces the two-character WRAP check; amended 2026-10-19, S2b, ADR-10)

Why the +1 check is gone: at n=5 triples per group the minimum detectable difference (normal approximation, two-sided 0.05, power 0.80) is 26.6 tokens at SD 15.0 and about 115.4 tokens at SD 65.1 (the WRAP SD of F1 attempt 1), so a difference of 1 token cannot be seen. The check that replaces it asks what the evaluation needs: whether a known change in instruction size is measured additively.

Fixed paths. Every invocation of a batch uses the same absolute config-directory path, `<temp_root>\ccfg`, and the same absolute working-directory path, `<temp_root>\cwork`, where `<temp_root>` is one fixed setting in `config.example.json`. Both names are fixed, so their length and bytes are identical in every run (hypothesis H1: varying directory names in imported-file headers and in the environment block change the token count). This overrides the "fresh directory" naming of section 2 step 1; isolation is kept by item 8: the previous run's directories are deleted and asserted absent before the next run creates them. The path is logged per run.

Doses. One block B is a fixed ASCII text written once by the builder into `harness\samples\dose-block.txt` (its md5 goes into the recipe), sized so that its content is at least 200 tokens. The dose file for k = 1, 2, 3, 4 is B repeated k times. For each k the harness runs 5 same-batch triples (BASE, ONECHAR, FILE with the dose file) in a seeded order across all 20 triples, and computes content as in section 2.

Pass rule, fixed before any run:
1. The mean content at k = 1 is at least 200 tokens. If it is lower, the builder doubles B once, records the new md5 and reruns; a second shortfall is reported, not corrected.
2. An ordinary least-squares fit of content on k over the 20 triples gives intercept a and slope b. The intercept lies within plus or minus 54 tokens of 0 (expected SE about 25 at SD 45).
3. Each of the 4 dose means lies within plus or minus 54 tokens of the fitted line a + b times k (expected SE of a dose mean about 20 at SD 45).

Report: the 20 triple values, content per triple, the mean and SD of content and of WRAP per dose, a, b, their standard errors, the residual SD and the verdict of each pass item. Any failure is reported, not corrected, and the pilot does not start until Adi decides.

### 6.2 F2 repeatability (the second check of ADR-10; run in S2c)

The unedited F2 is measured with 5 same-batch triples in two separate batches, using the fixed paths of 6.1. The two mean content values differ by at most 54 tokens (the F1 tolerance, unchanged). Both means, both SDs and the difference are reported; a larger difference is reported, not corrected, and the pilot does not start until Adi decides.

## 7. Reporting

The builder returns a CODEX REPORT on the console only (no file writes outside the harness folder). It lists, for each acceptance item, the test name, the command and the pasted result; the pin; every md5 (full 32 characters, computed by `Get-FileHash -Algorithm MD5` or `certutil`); the dry-run summary; the dose-response values and verdicts of section 6.1. A count, hash or existence claim appears only with the command output that shows it.

## 8. Not in scope

No edit to the token-aware skill or to `cost.py`. No use of a second rates reader. No run on a held-out task. No git command. No write under `.claude\`, `ops\sync\`, `_to_delete\` or `skills\`.

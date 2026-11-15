# Token-aware build environment (2026-10-19)

Python 3.13.14 replaces the Python 3.12 specified in both contracts, as authorised by the brief. Interpreter: C:\Users\REDACTED_USER\venvs\token-aware-eval\venv\Scripts\python.exe. The environment was created from the system Python only.

Observed pins from brief commands 1-12b: Node v24.18.0; npm 11.17.0; uv 0.12.0 (b88d7c5c4); pytest 9.1.1; numpy 2.5.4; scipy 1.18.1; Claude Code 2.1.303.

Exact installation commands (cmd.exe, each in its own process):

```cmd
uv venv C:\Users\REDACTED_USER\venvs\token-aware-eval\venv --python 3.13.14 --python-preference only-system
uv pip install --python C:\Users\REDACTED_USER\venvs\token-aware-eval\venv\Scripts\python.exe pytest numpy scipy
uv pip show --python C:\Users\REDACTED_USER\venvs\token-aware-eval\venv\Scripts\python.exe pytest numpy scipy
npm install --prefix C:\Users\REDACTED_USER\venvs\token-aware-eval\claude-code @anthropic-ai/claude-code@2.1.303
```

Recreation uses `uv pip install --python C:\Users\REDACTED_USER\venvs\token-aware-eval\venv\Scripts\python.exe pytest==9.1.1 numpy==2.5.4 scipy==1.18.1`. No global npm installation and no pip, conda or uv sync.

Every subprocess started by runlib.child, including version checks and task checks/graders, receives DISABLE_AUTOUPDATER=1 and CLAUDE_CONFIG_DIR=C:\Users\REDACTED_USER\venvs\token-aware-eval\tmp\ccfg. No auto-update settings file is written; the deviation 7 exception is not used. TEMP and TMP point to C:\Users\REDACTED_USER\venvs\token-aware-eval\tmp, and PYTHONDONTWRITEBYTECODE=1 prevents imported code from writing bytecode beside read-only inputs.

First-party documentation: https://code.claude.com/docs/en/env-vars : `DISABLE_AUTOUPDATER` — “Set to `1` to disable automatic background updates.” `CLAUDE_CONFIG_DIR` — “Override the configuration directory (default: `~/.claude`).”

The harness calls the pinned native executable directly, without cmd.exe: `C:\Users\REDACTED_USER\venvs\token-aware-eval\claude-code\node_modules\@anthropic-ai\claude-code\bin\claude.exe`. Its `--version` output was `2.1.303 (Claude Code)`. The `.cmd` shim integrity test failed because the T01 prompt's trailing newline was lost while forwarding a command-line argument. The direct-executable stub test passed for all three required prompts (OK, F2 edit prompt, full T01 task text), byte-identical including newlines; stdin reached EOF within one second in all three runs. The harness therefore uses only the direct native executable. No other launch-method change was made.

Each subprocess started by `runlib.child` receives `stdin=subprocess.DEVNULL`; Claude prompts are inserted as one `-p` command-line argument. Claude task invocations have a 900-second timeout. On timeout, runlib invokes `C:\Windows\System32\taskkill.exe /PID <owned pid> /T /F`, flags the record as `timeout`, and raises an error so the batch stops. The shortened 0.2-second sleeping-stub test passed, and the timeout-record integration test asserts the timeout flag and batch-stopping error.

Permission flags: `--permission-mode dontAsk --allowedTools Read,Edit,Write,Bash,Skill --tools Read,Edit,Write,Bash,Skill,Glob,Grep --strict-mcp-config`. They use normal permission checks, deny requests that would need interactive approval, limit the available tools, exclude external MCP configuration, and expose no web tools.

Deviation 9, lead ruling approved by Adi: native Windows has no OS-level sandbox for Claude Code's shell tool. The requirement that shell commands reach the working directory and nothing else is an accepted limitation. Containment is UNVERIFIED. The permission flags and all credential/deletion checks remain in force; a successful dry run will not change the containment label.

Shell prerequisites were run in cmd.exe before live runs. `where bash` printed `C:\Windows\System32\bash.exe`; `git --version` printed `git version 2.55.0.windows.3`; `where git` printed `C:\Program Files\Git\cmd\git.exe`. Git for Windows supplies the configured Bash tool. CLAUDE_CODE_GIT_BASH_PATH is set in subprocess environments to C:\Program Files\Git\bin\bash.exe, avoiding the WSL launcher found on PATH. This environment variable is documented at https://code.claude.com/docs/en/env-vars and https://code.claude.com/docs/en/setup. No settings file is written.

The fixed requested tool set is Read, Edit, Write, Bash, Skill, Glob, Grep in every invocation of every batch. Each run record contains shell_tool, configured_tool_set, permission_flags, observed_tools, shell_tool_confirmed and containment. The harness reads init.tools on every invocation, requires Bash, rejects an unexpected PowerShell or web tool, and requires the observed tool set to stay identical within the batch. The first live init event confirmed Bash and the exact requested tool set, though that first dry run failed its skill-set check.

Deviation 10, lead ruling: pinned Claude Code 2.1.303 reports these 19 bundled skills in `init.skills`: deep-research, design, design-sync, dataviz, update-config, verify, debug, code-review, simplify, batch, fewer-permission-prompts, doctor, loop, schedule, claude-api, workflow-authoring, run, run-skill-generator, plugin-authoring. The harness compares the arm's installed skill names plus exactly this set. Every init also must report exactly the built-in plugins `cc-plugin-agents-md`, `cc-plugin-telemetry`, `cc-plugin-plugin-authoring` (each with path `builtin`) and an empty `mcp_servers` list. These checks run on receipt of init; a mismatch terminates the harness-owned process tree immediately. Records preserve observed skills, plugins, MCP servers, and Skill tool calls.

The trigger skill name is read from the `name` frontmatter field of the token-aware `SKILL.md`; only Skill calls with that name set `triggered=true`. Calls to other skills, including bundled skills, remain recorded in `skill_calls` but do not count as triggers. The pinned package's `sdk-tools.d.ts` does not declare the built-in `Skill` tool or its input schema; it contains `| ProposeSkillsInput` at line 50, which concerns skill proposals and does not establish the runtime Skill input field. The stream parser therefore reads the runtime `tool_use.input.skill` field used by the harness's recorded event format; this SDK declaration limitation is reported as a conflict.

Pinned help confirms `-p`, `--output-format`, `--verbose`, `--model`, `--permission-mode dontAsk`, `--allowedTools`, `--tools` and `--strict-mcp-config`. https://code.claude.com/docs/en/cli-reference and https://code.claude.com/docs/en/permissions describe these flags. https://code.claude.com/docs/en/headless says each stream-json line is an event and the final result supplies response, cost and session metadata.

Layout: skills/<name>/SKILL.md and CLAUDE.md plus its relative imports in the isolated config directory, with credentials excluded from its sorted-path/byte SHA256 hash. Configuration is populated afresh at the same ccfg path and each invocation uses the same cwork path, then both paths are deleted and asserted absent. https://code.claude.com/docs/en/memory documents user-scope CLAUDE.md and relative imports; https://code.claude.com/docs/en/skills documents personal skills.

Parser evidence: https://github.com/anthropics/claude-agent-sdk-python/blob/main/src/claude_agent_sdk/_internal/message_parser.py and types.py define assistant tool_use blocks and final result fields. Synthetic samples are explicitly labelled in samples/provenance.md. They are not claimed as recorded live events. The configured init.skills string-list and Skill input.skill shape must be confirmed against recorded dry-run events; missing fields fail closed, without substitutions. Model ID is asserted exactly, while modelUsage may include auxiliary models and each is priced independently.

Content tokens = result.usage.input_tokens + result.usage.cache_creation_input_tokens + result.usage.cache_read_input_tokens. WRAP = ONECHAR - BASE - 1. Content = FILE - BASE - WRAP. Dose OLS uses all 20 triples; sample SD uses ddof=1 and residual SD has 18 degrees of freedom. On a k=1 mean below 200, B is doubled once and all 60 invocations rerun once. Other pass-item failures are reported without correction.

The analysis uses minimum of the five unedited probe scores and no 1/P allowance. A missing required second pass is an error; dry-run exception is explicitly labelled and not evaluation input. Seeds and all statistical constants are echoed. Input pins and cost flags are checked before statistics.

Rule-4 worked CVs are already upper-bounded CVs, per the lead's clarification. rule4_power and rule4_r take that bounded CV directly. The power report multiplies the pilot AN CV by sd_upper_factor(4) exactly once before passing it to rule4_r. All worked values remain unchanged. analyse() already merges CONSTANTS with preregistration settings before calling context_runs; its direct unit test now constructs the same merged configuration, without hidden defaults in context_runs.

Build status and MD5 manifest are appended at command 14 completion. A frozen recipe hash in prereg.md is for the lead; this build does not modify prereg.md.

Lead code-review fixes (R1-R6):

- R1: `_terminate_process_tree` checks taskkill's return code, falls back to `proc.kill()` on failure, waits up to five seconds, and raises `RunError("process tree termination failed")` if the child remains alive. That error stops the batch.
- R2: track-A triple invocations with a result turn count other than one are recorded with `multi_turn_triple` and stop the batch. Auxiliary models are recorded per run with input, output, cache-read and cache-creation token counts; they add `auxiliary_model` and do not stop the batch. Dry-run and dose-response summaries report the number of runs with auxiliary models.
- R3: edit records include each fixture file's byte size before and after, its changed status, and total bytes before and after. No changed file adds `edit_no_change` and continues.
- R4: installed token-skill key and directory name come from `token_skill_root\SKILL.md` frontmatter. `load_config` requires the frontmatter name to equal `trigger_skill`; init validation and trigger counting use that configured value.
- R5: each run record includes MD5 values for `harness.py`, `runlib.py`, and `pricing.py`; schema includes all three.
- R6: each invocation snapshots direct entries under the fixed temp root before and after. Newly appeared names are saved in `temp_leftovers`, excluding `ccfg`, `cwork`, `pytest`, and `step*.cmd`; no new entry is deleted.

The bad-init termination test uses `sys._base_executable` so the child process PID is the Python stub rather than a venv launcher.

Lead ruling on cache TTL pricing: `runlib.parse_stream` requires the result usage `cache_creation` object to contain nonnegative `ephemeral_5m_input_tokens` and `ephemeral_1h_input_tokens` whose sum equals `cache_creation_input_tokens`. Both values are recorded as `cache_write_5m` and `cache_write_1h`. Pricing requires a single model when a cache-write split is present, prices the 5-minute and 1-hour portions using their respective master rates, and records both write rates in `unit_rates`. A multi-model usage record fails closed as an ambiguous cache-write split. The existing 1 percent cost tolerance and assertion cap are unchanged.

ADR-14, deviation 11, approved by Adi: the harness passes `--settings` and the JSON object `{"syncClaudeAiSkills":false}` as separate Claude argv entries. Init validation explicitly rejects skill names in the `anthropic-skills:` namespace; expected bundled skills and plugin checks remain exact.




## Command 14 artifact MD5 manifest (2026-10-19 build, superseded; kept as the pre-amendment record)
harness.py: a591e452935d41a01e65865dbc6f6445
runlib.py: 0d539a929e154fa8b1d8a02829f84294
pricing.py: 61aa5f770825dbc930142589dfd2a9ce
test_harness.py: 28b5b432ebee0d4eb031f62fbee539fe
analysis.py: 152b6618e6b2caa1b709a891b268a8e6
test_analysis.py: 2dac37ff14d4e79fbfd9ebe1f56a936e
config.example.json: 2194f8d622f8ee295f1c56ec4814f938
samples/dose-block.txt: 9412b8d69e37a4dcf3ea74b8d2b0d433

ADR-15 (2026-10-20), deviation 12, supersedes the deviation 10 list above: every invocation passes `--settings {"syncClaudeAiSkills":false,"disableBundledSkills":true,"skillOverrides":{"doctor":"off"}}`; the expected bundled set is exactly {design, plugin-authoring} (BUNDLED_SKILLS) and init validation stays exact.

ADR-16 (2026-10-20): runs authenticate with a one-year token from `claude setup-token`, read by `runlib.child_env` from `C:\Users\REDACTED_USER\ClaudeHarnessSecrets\oauth-token.txt` into `CLAUDE_CODE_OAUTH_TOKEN`; CLAUDE_CODE_USE_BEDROCK, CLAUDE_CODE_USE_VERTEX, CLAUDE_CODE_USE_FOUNDRY, ANTHROPIC_AUTH_TOKEN, ANTHROPIC_API_KEY and ANTHROPIC_BASE_URL are stripped from the child environment; the token's literal and JSON-escaped forms are needles (harness-spec item 7 amended). Amendment 2 (2026-10-23): the harness copies no credentials file into the config directory; `credentials_file` remains a needle source and every file in ccfg is scanned by `credential_check`; strings found in a `ccfg\.credentials.json` written during a run join the needles before redaction.

ADR-17 (2026-10-21): a needle is dropped only when every label on it names a field in NON_SECRET_FIELDS = {claudeAiOauth.rateLimitTier}; the tier name joins the scrub check (R11) before publication (harness-spec item 7 amended with ADR-16).

ADR-18 (2026-10-21): every live run is started by Adi from a plain cmd window with the venv interpreter; `runlib` refuses a launch when any environment variable name starts with `CODEX_`. The live-run line is `cmd /d /c "cd /d C:\Users\REDACTED_USER\Documents\ClaudeSkills\notes\token-aware\eval\harness && C:\Users\REDACTED_USER\venvs\token-aware-eval\venv\Scripts\python.exe harness.py <command> --config config.example.json > C:\Users\REDACTED_USER\Documents\ClaudeSkills\notes\token-aware\eval\logs\build\<name>.txt 2>&1"`. Codex applies lead-written, md5-pinned patches and runs pytest only, launched with `codex --cd C:\Users\REDACTED_USER\Documents\ClaudeSkills --sandbox workspace-write --add-dir C:\Users\REDACTED_USER\venvs\token-aware-eval -c sandbox_workspace_write.network_access=true`. Amendment 1 (2026-10-23): an IN denial (ADR-19 scope, computed in `runlib.denial_scope`) flags the run `permission_denied`, voids it and stops the batch at once after the record is written; the A48 three-consecutive rule is retired. Amendment 2 (2026-10-23): an OUT denial of Glob or Grep is recorded in `permission_denials` (`in_count`, `out_count`, `out_other`, `in_targets`) and neither flags nor voids the run.

ADR-19 (2026-10-21): RAID I4 closing rule A52 v2, judged by the pinned read-only classifier (`prepared\a52v2-classifier.v3.py` fde12669b170f6f68e61ca106d54ffea for batches in the S2e-S2f harness state; `prepared\a52v2-classifier.v4.py` 048482429f953caa9bdbbed420d12ee5 for S2g batches). ADR-20 (2026-10-22): fixtures F2 and F3 trigger lines anchored to the folder that holds CLAUDE.md; pool list `eval\pool-tree-md5-2026-10-22.txt` e4d00b93d244af6ea191d58d58129af5, archive `eval\eval-pool-2026-10-22.zip` 7d7915811d9b22583324e603e9ed94ef.

ADR-21 (2026-10-23): each record carries `launcher` (interpreter, argv[0], cwd, CODEX_* names, console markers as booleans; captured at batch INIT) and `config_files` (md5 of `ccfg\policy-limits.json` and `ccfg\remote-settings.json` after the child exits, null when absent). ADR-10 amendment 3 (2026-10-23): each record carries `event_counts` (assistant, user, system, result); a track A triple with more than one assistant or result event is flagged `multi_request_triple` and stops the batch like `multi_turn_triple`.

Harness states: S2e-S2f (runlib 185e69004fb466af15980fd7f7113fb0, harness 3e7d6d7fc1a4fab873bdaa6a939a44a4) ran batches 20261021T090728-3ed92e1d, 20261021T114109-9c092dc2, 20261022T101112-3f472f1e and 20261022T111520-356dcdbc; S2g (the manifest below, after `prepared\s2g-harness-patch.py` 904480d8e81126b50f69407a7766dd8c and `prepared\s2g-bundle-patch.py` fc47502e532789b917a75ea8a66ea40d, 102 tests passed on 2026-10-23) has run no batch yet; its first dry run, started by Adi, validates ADR-16 amendment 2 before Gate S2.

## MD5 manifest (regenerated 2026-10-23, S2g state; supersedes the command 14 manifest)
harness.py: 3e896ad21cf33a4c79199d5ca16f966c
runlib.py: ce4c6cac89549a1018de1a8d3945179d
pricing.py: 1b03ec48a32b857218a9280e819428d1
test_harness.py: 8799f18122032d9804ae9f2cd65407c8
analysis.py: 94ac2575d1276c1e0efb0c81092d6976
test_analysis.py: a6b65bfc3e038391e545c2ace7d84deb
conftest.py: ff75a46849b019a5e32ad805b475e02f
config.example.json: 2194f8d622f8ee295f1c56ec4814f938
samples/dose-block.txt: 9412b8d69e37a4dcf3ea74b8d2b0d433
analysis-fixtures/pilot.json: 910f3e8f16ce68c4e2e6d36d19df00ce
analysis-fixtures/prereg.json: 4ada726b73dc5a60899aa855a5fb97a4
analysis-fixtures/records.json: aa8ebcf2129cb61cf51da62da4be15d7

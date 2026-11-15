# Metering: measured actuals beside estimates | v1.3 | 2026-09-29 | review by 2026-10-28

An estimate that never meets a measured actual cannot be scored, and a skill whose figures cannot be scored is asserting, not measuring. This file names where actuals come from and how `tools/cost.py` pairs them with estimates. Read it before putting any cost figure in a report.

## The rule

A cost figure enters a report only beside a measured actual, or labelled "estimate, no actual". Log the estimate first, then the actuals, under the same `--site` label, and run `python tools/cost.py pairs`. Each estimate is paired with the actuals logged after it and before the next estimate for that site, so a reused label starts a fresh window; actuals logged before any estimate stay unpaired. Below 5 pairs the output is labelled a small sample; say so wherever the number is quoted.

## Sources of actuals, by surface

| Surface | Source | What it measures | How to log it |
|---|---|---|---|
| API pipeline you own | `response.usage` on every call (`input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation` 5m and 1h) | exact billed tokens per call | `cost.py cost ... --actual --method usage --site <site> --log` |
| Claude Code through a Headroom proxy | the proxy's `GET /stats` (`recent_requests`, `cost.per_model`, `prefix_cache.totals`) | tokens before and after compression per request; cache writes per model and reads since the last run | `cost.py headroom --site <site> --log` |
| Claude Code without a proxy | ccusage (`npx ccusage@latest session`), which reads Claude Code's local JSONL | tokens per session after the fact | `cost.py cost ... --actual --method ccusage --site <site> --log` |
| Before a call, any surface with an API key | Anthropic `count_tokens` endpoint, free, rate-limited per tier | input tokens for one request (documented as an estimate that "might differ by a small amount") | calibration only, never logged as an actual: compare with `cost.py estimate`, see `module_layout.md` |
| Hosted chat (claude.ai, Cowork) | none exposed per request | nothing billable per token on a subscription | estimates only, labelled as such |

Subscription plans (Claude Pro, Max, Team seats) are not billed per token. Dollar figures for work run on them are list-price comparisons for sizing and ranking, never spend; say which in the report, per `SKILL.md` § What this skill does not do.

## Headroom proxy

Headroom (Apache 2.0) is a context-compression proxy that sits between the client and the provider. For this skill it does two separate jobs.

**It performs TRIM and part of CACHE at the transport layer.** Its compressors shrink tool outputs, logs, diffs and, with the `[code]` extra installed, code; its CacheAligner stabilises message prefixes so provider caching hits more often. An audit of a pipeline that already runs through it credits those savings to the proxy and looks for what remains. Recommending the same cut again double-counts.

**It is a meter.** `/stats` reports `input_tokens_original` and `input_tokens_optimized` per request, and cumulative cache writes per model. `cost.py headroom` takes only token counts and prices them against `rates.json`. Cache counters are cumulative for the proxy's lifetime, so each run logs the delta since the last snapshot and treats a lower counter as a restart. `recent_requests` is a rolling window: run the command after every session, and it warns when requests have rotated out unlogged. It does not use Headroom's dollar figures: on 2026-09-28 its `/stats` priced 107,551 one-hour cache-write tokens on Opus 5 at the 5-minute premium ($0.672 session total) where the first-party 1-hour rate is 2x base input ($1.076 for the writes alone).

**Accuracy gate.** Compression of structured output is lossy unless retrieval is in play (Headroom's CCR mode keeps originals retrievable). Treat it like a REPLACE on protected calls (`SKILL.md` § Protected calls): run a sample with the proxy on and off and compare outputs before trusting it there. Headroom's published benchmarks are its own.

**Operating notes.**

- The proxy sees every prompt and the client's auth token, so treat the image like a credential store. Pin it by digest rather than `:latest`, bind it to loopback only, and keep telemetry off:

```powershell
docker pull ghcr.io/chopratejas/headroom:latest
docker inspect --format "{{index .RepoDigests 0}}" ghcr.io/chopratejas/headroom:latest   # record this digest
docker run -d --name headroom-proxy -p 127.0.0.1:8787:8787 --restart unless-stopped `
  -e HEADROOM_TELEMETRY=off -v headroom-data:/root/.headroom ghcr.io/chopratejas/headroom@sha256:<digest>
```

- The documentation lives under `headroomlabs-ai` and the image under `chopratejas`; confirm on the project's own README that the image namespace is the official publisher before pinning.
- `/stats` lifetime figures live in `/root/.headroom/proxy_savings.json` inside the container; the volume above keeps them across a recreate.
- `/stats` reported a rate limiter of 100,000 tokens per minute on a default install (2026-09-28), below a single large Opus request and below many long Claude Code turns on the 200k window. Headroom 0.39.0 documents `--no-rate-limit` as the flag that disables the limiter (upstream issue #1350); confirm it with `headroom proxy --help` on the pinned image, and decide on it before the next long session, not only before a 1M-context one.
- A persistent `ANTHROPIC_BASE_URL` pointing at a stopped proxy breaks every client. Prefer a launcher that checks `GET /readyz` and falls back to direct routing:

```powershell
function claudeh {
    $running = docker inspect -f "{{.State.Running}}" headroom-proxy 2>$null
    $code = curl.exe -s -o NUL -w "%{http_code}" http://127.0.0.1:8787/readyz
    if ($running -eq 'true' -and $code -eq '200') { $env:ANTHROPIC_BASE_URL = 'http://127.0.0.1:8787' }
    else { Write-Warning 'Headroom down, running direct'; Remove-Item Env:ANTHROPIC_BASE_URL -ErrorAction SilentlyContinue }
    claude @args
}
```

- Any hook or script that calls the API itself (a Stop hook, a memory updater) must read `ANTHROPIC_BASE_URL` rather than hardcoding `api.anthropic.com`, or it bypasses the proxy and the meter.

## Session routine

1. Before a priced session: `python tools/cost.py cost --model <id> --in <est> --out <est> --site <label> --log`.
2. After it: `python tools/cost.py headroom --site <label> --log` (or the ccusage line above).
3. After each metered session, for every shipped plan with actuals in its window: `uv run --python 3.14 tools/cost.py realise --id S-... --auto` (with `--supersede R-...` to rescore a plan already realised).
4. Weekly: `python tools/cost.py pairs`, `python tools/cost.py verify` for figures computed on since-expired tables, `python tools/cost.py check` for price drift, and `uv run --python 3.14 tools/cost.py score --out <path>` for the scoreboard (`--out` because a PowerShell 5.1 `>` redirect writes UTF-16).

## Keeping prices current

Prices are not updated automatically, by design: `rates.json` changes only from the first-party pricing page, by hand, with a new `verified` date and dated provenance per fact. What is automatic is the refusal: `cost.py` warns 7 days before `expires`, warns on any fact older than 30 days, and refuses past `expires` or past 90 days for any fact. `python tools/cost.py check` compares the table with LiteLLM's community price map and exits 1 on any disagreement, which makes it suitable for a scheduled job; the map is secondary, so a disagreement is a prompt to re-read the first-party page, never a value to copy. Models absent from the map are listed as unchecked.

## Scoreboard

Every optimisation this skill recommends is recorded twice: the saving predicted before it ships and the saving realised after it. `cost.py score` reports the two side by side, so the skill's own predictions get scored the way its estimates do.

**Records.** Three record kinds join the log, none carrying `usd`. `cost.py plan` writes the prediction when a change is decided: the `site` its actuals are logged under, the `lever` (BATCH, REPLACE, DOWNGRADE, CACHE, TRIM or PROXY), the `method` the saving will be computed by, `predicted_usd` per `unit` (`call` or `day`, and `plan` refuses a prediction of zero or less), `predicted_basis`, `billing` (`metered`, `subscription` or `unknown`), and for DOWNGRADE the `baseline_model` and `after_model`. `cost.py ship --id S-...` writes the go-live moment; `--at` records an earlier real go-live date, and only a `post_hoc` plan (one written after its change was already live, such as the first Headroom plan) may ship before it was planned. `cost.py realise --id S-...` writes the score over the window. Each realised record names the plan, the `evidence` class, the window, the record counts on each side, the input tokens per call on each side so a change in workload stays visible, and an optional one-line `lesson`. The log stays append-only: a rescoring is a new record with `supersedes` naming the earlier one, and `score` reads only the newest per plan.

**Rules.**

1. The prediction is written before the change ships: `realise` refuses a plan whose `ts` is later than its shipped record's, and only actuals from `live_from` onwards are scored. The check has a limit: a plan written after its change went live and shipped without `--post-hoc` puts post-change actuals in the before window, and nothing in the log can detect it, so `--post-hoc` is the operator's discipline.
2. The evidence classes `measured`, `modelled-baseline` and `estimate` are never summed. `measured` means priced actuals on both sides of the change; `before-after` is the only method that earns it.
3. Dollars on `subscription` or `unknown` billing are list-price equivalents and are labelled `list-price` in the score; they are never spend.
4. A REPLACE whose plan carries no `agreement` rate is reported as `unaudited`, whatever it saved.
5. Headroom is priced from its token counts through `rates.json`, never from its own dollar figures.
6. Both sides of every comparison are repriced under the current `rates.json`, so a price change never reads as a saving.

**Windows and time.** Actuals are filtered on `request_ts` when present, otherwise on `ts`; a trailing `Z` is read as `+00:00` and a naive value as UTC; a record whose time does not parse is skipped and counted in the output. The before window is the 14 days ending at `live_from`. The after window runs from `live_from` to the earlier of 14 days later and `--until` (default now) for `before-after` and `headroom-cache`; for `headroom-proxy` and `manual` it runs to `--until` with no cap, so a rescoring covers the whole period to date. A plan site of `claude-code` also matches session labels under it, such as `claude-code:2026-09-28-say-hi`.

**Methods.**

| method | levers | computation | evidence |
|---|---|---|---|
| `before-after` | BATCH, DOWNGRADE, TRIM, CACHE on an owned pipeline | cost per call on each side, from records with `calls > 0` repriced through `cost()` with every logged field (`tool_choice` included, so a TRIM that drops tools keeps its overhead saving); for DOWNGRADE the before side is priced at `baseline_model`; saving is the per-call difference times the calls after; both sides need `--min-n` records (20 by default) | `measured` |
| `headroom-proxy` | PROXY | the sum over proxied requests after `live_from` of the cost at `in_tokens_original` minus the cost at `in_tokens`; beside it, cache spend per request before against after, flagged `CACHE COST ROSE` when it increased or `NO BEFORE DATA` when the before window holds no cache records | `modelled-baseline` |
| `headroom-cache` | CACHE through Headroom | net cache saving per request (reads at one minus the model's read multiplier, less the 5-minute and 1-hour write premiums) after minus before, times the requests after; requests come from `requests_delta`; both sides need `--min-n` requests; a negative result is kept | `modelled-baseline` |
| `manual` | any lever; the only method for REPLACE | `--realised-usd` with `--basis`; REPLACE adds `--calls-replaced` from the application's own logs; `--evidence` may only lower the class and is refused when it names `measured` | `modelled-baseline` with `--calls-replaced`, otherwise `estimate` |

The per-unit figure divides the realised saving by the calls on the after side for `unit: call` (the requests, for `headroom-cache`; `--calls-replaced`, for `manual`) and by the window's days for `unit: day`. A `post_hoc` plan has no unit and no per-unit figure.

**`cost.py score`** prints the log path, the rates `verified` date, the billing mix, the plans not yet shipped and the shipped plans not yet realised; savings by lever and billing with USD and `n` in separate `measured`, `modelled-baseline` and `estimate` columns and no total across them; prediction accuracy per lever and evidence class (the median of realised over predicted per unit and the mean absolute percentage error, with `small sample` below 5, `post_hoc` plans excluded); every zero-or-negative saving with its lesson; REPLACE plans without an agreement rate as `unaudited`; and the 10 newest lessons. `--since`, `--site` and `--lever` filter; `--json` gives the same as data; `--out PATH` writes UTF-8 without a BOM. `score` reads only the `verified` date from `rates.json`, so it still prints on an expired table, while `plan`, `ship` and `realise` refuse on one like every other priced command.

## Log schema

One JSON object per line in `tools/cost_log.jsonl`, or at `$TOKEN_AWARE_LOG` when set (point it outside the skill folder, for example `<skills-root>/ops/token-aware/cost_log.jsonl`, beside `skills/` rather than inside it, so private usage never ships with the skill, its zip or its public copy; set it once, persistently, so every copy of the skill reads and writes the same ledger). Written only by `cost.py`.

| field | meaning |
|---|---|
| `site` | the label that pairs an estimate with its actuals |
| `kind` | `estimate`, `actual`, `snapshot`, `plan`, `shipped` or `realised`; records from before v2.4 have none, and only `headroom /stats (per-request, cache excluded)` among them counts as an actual |
| `model`, `in_tokens`, `out_tokens`, `calls`, `cache_read`, `cache_write`, `ttl`, `region`, `tool_choice`, `batch` | the inputs, so the figure can be recomputed |
| `method` | how the token counts were obtained |
| `via_headroom` | the call went through the proxy |
| `usd` | the figure, priced by `rates.json` |
| `rates_verified`, `rates_expires`, `excluded_modifiers`, `ts` | the table the figure was computed against |
| `request_id`, `in_tokens_original`, `usd_without_headroom` | Headroom per-request records |
| `cache_write_5m`, `cache_write_1h`, `cache_snapshot` | Headroom cache records and the cumulative counters they were diffed against |
| `requests_delta` | requests since the previous snapshot (the whole count after a restart), stored once per `headroom --log` run on the record carrying `cache_snapshot` or on the `snapshot` record; the denominator for per-request cache figures |
| `kind: plan` with `id`, `lever`, `method`, `predicted_usd`, `unit`, `predicted_basis`, `billing`, `post_hoc`, `baseline_model`, `after_model`, `agreement`, `agreement_n` | the prediction, written before the change ships (§ Scoreboard) |
| `kind: shipped` with `plan_id`, `live_from` | the go-live moment; `live_from` is `ts` unless `ship --at` gave an earlier real date |
| `kind: realised` with `id`, `plan_id`, `method`, `evidence`, `realised_usd`, `realised_per_unit`, `realised_basis`, `calls_replaced`, `window_start`, `window_end`, `days`, `n_before`, `n_after`, `calls_before`, `calls_after`, `tokens_per_call_before`, `tokens_per_call_after`, `skipped_times`, `supersedes`, `lesson` | the score over the window; `score` reads the newest per plan |

## Comparable tools (accessed 2026-09-28)

| Tool | Role | Source |
|---|---|---|
| Anthropic `count_tokens` | free pre-call input count | https://platform.claude.com/docs/en/build-with-claude/token-counting |
| ccusage (MIT) | Claude Code usage from local JSONL, LiteLLM prices | https://github.com/ryoppippi/ccusage |
| LiteLLM | community price map, `completion_cost` | https://docs.litellm.ai/docs/completion/token_usage |
| tokencost (MIT) | pre-call estimates, Anthropic counting API for Claude 3+ | https://github.com/AgentOps-AI/tokencost |
| Langfuse | ingested usage, model price definitions with a daily audit | https://langfuse.com/docs/observability/features/token-and-cost-tracking |
| Helicone | gateway metering, open-source cost repository | https://docs.helicone.ai/guides/cookbooks/cost-tracking |
| Headroom (Apache 2.0) | compression proxy with `/stats` metering | https://headroomlabs-ai.github.io/headroom/ |

None of these refuses to compute on a stale price; `cost.py` does, per table and per fact. That is the part of this skill worth keeping as it is.

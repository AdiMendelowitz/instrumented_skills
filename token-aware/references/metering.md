# Metering: measured actuals beside estimates | v1.1 | 2026-09-28 | review by 2026-10-28

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
- `/stats` reported a rate limiter of 100,000 tokens per minute on a default install (2026-09-28), below a single large Opus request; check `headroom proxy --help` for the flag before relying on it for 1M-context sessions.
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
3. Weekly: `python tools/cost.py pairs`, `python tools/cost.py verify` for figures computed on since-expired tables, and `python tools/cost.py check` for price drift.

## Keeping prices current

Prices are not updated automatically, by design: `rates.json` changes only from the first-party pricing page, by hand, with a new `verified` date and dated provenance per fact. What is automatic is the refusal: `cost.py` warns 7 days before `expires`, warns on any fact older than 30 days, and refuses past `expires` or past 90 days for any fact. `python tools/cost.py check` compares the table with LiteLLM's community price map and exits 1 on any disagreement, which makes it suitable for a scheduled job; the map is secondary, so a disagreement is a prompt to re-read the first-party page, never a value to copy. Models absent from the map are listed as unchecked.

## Log schema

One JSON object per line in `tools/cost_log.jsonl`, or at `$TOKEN_AWARE_LOG` when set (point it outside the skill folder, for example `<project>/.claude/token-aware/cost_log.jsonl`, so private usage never ships with the skill). Written only by `cost.py`.

| field | meaning |
|---|---|
| `site` | the label that pairs an estimate with its actuals |
| `kind` | `estimate`, `actual` or `snapshot`; records from before v2.4 have none, and only `headroom /stats (per-request, cache excluded)` among them counts as an actual |
| `model`, `in_tokens`, `out_tokens`, `calls`, `cache_read`, `cache_write`, `ttl`, `region`, `tool_choice`, `batch` | the inputs, so the figure can be recomputed |
| `method` | how the token counts were obtained |
| `via_headroom` | the call went through the proxy |
| `usd` | the figure, priced by `rates.json` |
| `rates_verified`, `rates_expires`, `excluded_modifiers`, `ts` | the table the figure was computed against |
| `request_id`, `in_tokens_original`, `usd_without_headroom` | Headroom per-request records |
| `cache_write_5m`, `cache_write_1h`, `cache_snapshot` | Headroom cache records and the cumulative counters they were diffed against |

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

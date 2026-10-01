"""Cost arithmetic for the token-aware skill.

Deterministic arithmetic belongs in Python, not in prose: this module exists because a
break-even claim written by hand contradicted the multipliers printed beside it.

Canonical rates live in rates.json. No figure is returned from an expired table, and no
fact older than FACT_MAX_DAYS is used. Every computed figure can be appended to
cost_log.jsonl with the rate-table date and the token-count method, so it can be
recomputed later and paired with a measured actual.

Network access happens only when asked: `headroom` reads a local Headroom proxy's /stats,
and `check` reads LiteLLM's community price map to flag drift. Neither writes rates.json;
a price change is applied by hand from the first-party page, then re-dated.

Subcommands: cost, breakeven, compare, estimate, verify, render, cpd, headroom, pairs, check,
plan, ship, realise, score. The last four are the savings scoreboard: a saving is predicted
before a change ships and scored after it, with evidence classes kept apart (metering.md).
Standard library only, tested on Python 3.14.
Version 2.5.1 (2026-09-29): one LEDGER_KINDS constant; no __future__ import.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
RATES_PATH = HERE / "rates.json"
# The log holds private usage records. TOKEN_AWARE_LOG moves it out of the skill folder
# (for example to <skills-root>/ops/token-aware/cost_log.jsonl, beside skills/ rather than inside it)
# so it never ships with the skill, its zip or its public copy.
LOG_PATH = Path(os.environ["TOKEN_AWARE_LOG"]) if os.environ.get("TOKEN_AWARE_LOG") else HERE / "cost_log.jsonl"

WARN_WINDOW_DAYS = 7
FACT_WARN_DAYS = 30   # a provenance date older than this warns
FACT_MAX_DAYS = 90    # older than this refuses, like an expired table

CHARS_PER_TOKEN_PROSE = 3.5
CHARS_PER_TOKEN_CODE = 2.5
BUDGET_SAFETY = 0.8  # shrinks chars/token, so estimates run high, per module_layout.md
# First-party: Claude 4.7 and later use a tokenizer producing ~30% more tokens for the same
# text. 3.5 * 0.8 = 2.8 chars/token sits above 3.5 / 1.3 = 2.69, so without this factor the
# "deliberate over-estimate" under-counts by ~4% on current models. Per-model values live
# in rates.json `tokenizer_factor`; this is the conservative default when none is recorded.
NEWER_TOKENIZER_FACTOR = 1.3

HEADROOM_STATS_URL = "http://localhost:8787/stats"
LITELLM_PRICES_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
# Records written before v2.4 carry no `kind`; only this exact method counts as an actual.
LEGACY_ACTUAL_METHODS = {"headroom /stats (per-request, cache excluded)"}


class RatesExpired(RuntimeError):
    """Raised when the rate table or one of its facts is too old; a stale figure must not reach a report."""


class UnknownModel(KeyError):
    """Raised for a model absent from the table, rather than guessing a rate."""


@dataclass(frozen=True)
class Rates:
    verified: str
    expires: str
    source: str
    models: dict
    multipliers: dict
    modifiers: dict
    provenance: dict

    def _model(self, model: str) -> dict:
        try:
            return self.models[model]
        except KeyError:
            raise UnknownModel(
                f"{model!r} is not in rates.json. Add it with a verified date rather than assuming a rate."
            ) from None

    def rate(self, model: str) -> tuple[float, float]:
        m = self._model(model)
        return float(m["in"]) / 1e6, float(m["out"]) / 1e6

    def cache_read_mult(self, model: str | None = None) -> float:
        """Per-model override where the pricing page lists one, else the table default."""
        default = float(self.multipliers["cache_read"])
        if model is None:
            return default
        return float(self._model(model).get("cache_read_mult", default))

    def tokenizer_factor(self, model: str) -> float:
        """Tokens per legacy-tokenizer token; unrecorded models get the conservative default."""
        return float(self._model(model).get("tokenizer_factor", NEWER_TOKENIZER_FACTOR))

    def tool_overhead(self, model: str, tool_choice: str) -> int:
        """System-prompt tokens added to any tool-enabled request, per model."""
        key = "any" if tool_choice in ("any", "tool") else "auto"
        table = self._model(model).get("tool_overhead")
        if table is None or key not in table:
            raise UnknownModel(
                f"no tool-use overhead recorded for {model!r} ({key}); add it from the pricing page "
                f"rather than costing a tool-enabled call as if it were free."
            )
        return int(table[key])

    def excluded_modifiers(self) -> list[str]:
        """Null modifiers are excluded from every calculation and named in the output."""
        return sorted(k for k, v in self.modifiers.items() if v is None)

    def secondary_facts(self) -> list[str]:
        return sorted(k for k, v in self.provenance.items() if v.get("class") in ("secondary", "unverified"))

    def fact_ages(self, today: date) -> dict[str, int]:
        """Age in days of every dated provenance entry."""
        out = {}
        for k, v in self.provenance.items():
            d = v.get("date")
            if d:
                out[k] = (today - date.fromisoformat(d)).days
        return out


def load_rates(path: Path | None = None, today: date | None = None) -> Rates:
    """Load the table, warning inside the expiry window and refusing past it.

    path defaults to the module-level RATES_PATH, resolved at call time rather than at
    import time, so overriding cost.RATES_PATH (directly or via monkeypatch) takes effect.
    Freshness is checked per fact as well as per table: a table re-dated without
    re-checking its older facts would otherwise pass them off as current.
    """
    path = path or RATES_PATH
    today = today or date.today()
    data = json.loads(path.read_text(encoding="utf-8"))
    expires = date.fromisoformat(data["expires"])
    if today > expires:
        raise RatesExpired(
            f"rates.json expired {expires.isoformat()}; re-verify against {data['source']} "
            f"and update 'verified' and 'expires' before computing anything."
        )
    if today >= expires - timedelta(days=WARN_WINDOW_DAYS):
        print(f"WARNING: rates.json expires {expires.isoformat()}; re-verify soon.", file=sys.stderr)
    r = Rates(
        verified=data["verified"],
        expires=data["expires"],
        source=data["source"],
        models=data["models"],
        multipliers=data["multipliers"],
        modifiers=data.get("modifiers", {}),
        provenance=data.get("provenance", {}),
    )
    ages = r.fact_ages(today)
    dead = sorted(k for k, a in ages.items() if a > FACT_MAX_DAYS)
    if dead:
        raise RatesExpired(
            f"facts older than {FACT_MAX_DAYS} days: {', '.join(dead)}; re-verify them and update "
            f"their provenance dates before computing anything."
        )
    old = sorted(k for k, a in ages.items() if a > FACT_WARN_DAYS)
    if old:
        print(
            f"WARNING: facts older than {FACT_WARN_DAYS} days: "
            + ", ".join(f"{k} ({ages[k]}d)" for k in old),
            file=sys.stderr,
        )
    if r.secondary_facts():
        print(
            "WARNING: unverified/secondary-class facts still in the table: " + ", ".join(r.secondary_facts()),
            file=sys.stderr,
        )
    return r


def _check_non_negative(**values: float) -> None:
    for name, v in values.items():
        if v < 0:
            raise ValueError(f"{name} must be non-negative, got {v}")


def cost(
    rates: Rates,
    model: str,
    in_tokens: float,
    out_tokens: float,
    calls: int = 1,
    batch: bool = False,
    cache_read_tokens: float = 0.0,
    cache_write_tokens: float = 0.0,
    cache_ttl: str = "5m",
    region: str = "global",
    tool_choice: str | None = None,
) -> float:
    """Modelled cost in USD for `calls` identical calls.

    in_tokens counts uncached input only; cached input is passed separately so the
    multipliers apply where they actually apply. Output always bills at full rate.
    Cache reads use the model's own multiplier where the pricing page lists one.

    tool_choice adds the tool-use system prompt overhead for that model, which no prompt
    edit removes; region='us' applies the data-residency multiplier to every category.
    A model with no recorded overhead raises rather than assuming zero.
    """
    _check_non_negative(
        in_tokens=in_tokens, out_tokens=out_tokens, cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
    )
    if calls < 0:
        raise ValueError(f"calls must be non-negative, got {calls}")
    if cache_ttl not in ("5m", "1h"):
        raise ValueError("cache_ttl must be '5m' or '1h'")
    if region not in ("global", "us"):
        raise ValueError("region must be 'global' or 'us'")
    rate_in, rate_out = rates.rate(model)
    in_tokens += rates.tool_overhead(model, tool_choice) if tool_choice else 0
    write_mult = rates.multipliers["cache_write_5m"] if cache_ttl == "5m" else rates.multipliers["cache_write_1h"]
    per_call = (
        in_tokens * rate_in
        + cache_read_tokens * rate_in * rates.cache_read_mult(model)
        + cache_write_tokens * rate_in * write_mult
        + out_tokens * rate_out
    )
    if batch:
        per_call *= rates.multipliers["batch"]
    if region == "us":
        if rates.models[model].get("region_us") is False:
            raise ValueError(f"inference_geo 'us' pricing does not apply to {model!r}; see rates.json notes")
        per_call *= rates.multipliers["region_us_only"]
    return per_call * calls


def cache_breakeven_reads(rates: Rates, ttl: str = "5m", model: str | None = None) -> int:
    """Smallest number of re-reads after the write at which caching is cheaper.

    Compares n+1 uncached sends against one write plus n reads, on the cached prefix only.
    """
    write = rates.multipliers["cache_write_5m"] if ttl == "5m" else rates.multipliers["cache_write_1h"]
    read = rates.cache_read_mult(model)
    n = 1
    while write + n * read >= n + 1:
        n += 1
        if n > 1000:  # multipliers would have to be absurd; fail loudly rather than hang
            raise ValueError("no break-even under 1000 reads; check the multipliers")
    return n


def compare(rates: Rates, model_a: str, model_b: str) -> dict:
    """Ratio of a to b, per direction. Above 1.0 means a is the more expensive."""
    a_in, a_out = rates.rate(model_a)
    b_in, b_out = rates.rate(model_b)
    if b_in == 0 or b_out == 0:
        raise ValueError(f"{model_b} has a zero rate; ratio undefined")
    return {"in_ratio": a_in / b_in, "out_ratio": a_out / b_out}


def estimate_tokens(text: str, code: bool = False, tokenizer_factor: float = NEWER_TOKENIZER_FACTOR) -> int:
    """Deliberate over-estimate for budgeting only, never a billing figure.

    tokenizer_factor scales for the model's tokenizer (1.0 for pre-4.7 models). Validate
    against count_tokens after any model change; see module_layout.md.
    """
    base = CHARS_PER_TOKEN_CODE if code else CHARS_PER_TOKEN_PROSE
    return int(len(text) / (base * BUDGET_SAFETY) * tokenizer_factor)


def log_record(rates: Rates, record: dict, path: Path | None = None) -> dict:
    """Append one calculation, carrying everything needed to recompute it later."""
    path = path or LOG_PATH
    record = dict(record)
    record.update(
        ts=record.get("ts") or datetime.now().astimezone().isoformat(timespec="seconds"),
        rates_verified=rates.verified,
        rates_expires=rates.expires,
        excluded_modifiers=rates.excluded_modifiers(),
    )
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def verify_log(path: Path | None = None, today: date | None = None) -> list[dict]:
    """Every logged figure computed against a table that has since expired."""
    path = path or LOG_PATH
    today = today or date.today()
    if not path.exists():
        return []
    stale = []
    for rec in _read_jsonl(path):
        exp = rec.get("rates_expires")
        if exp and date.fromisoformat(exp) < today:
            stale.append(rec)
    return stale


def render_table(rates: Rates) -> str:
    """The pricing.md snapshot. Generated, so the copy cannot drift from the canonical table."""
    lines = [
        f"<!-- generated by: python tools/cost.py render | verified {rates.verified} | expires {rates.expires} -->",
        "",
        "| Model | Input | Output | Cache read | Min cacheable | Tokenizer factor |",
        "|---|---|---|---|---|---|",
    ]
    for name, m in rates.models.items():
        mc = m.get("cache_min_tokens")
        lines.append(
            f"| `{name}` | ${m['in']:.2f} | ${m['out']:.2f} | {rates.cache_read_mult(name)}x "
            f"| {mc if mc is not None else 'not measured'} | {rates.tokenizer_factor(name)} |"
        )
    lines += ["", f"Source: {rates.source} (first-party, {rates.verified}). Multipliers: " + ", ".join(
        f"{k} {v}x" for k, v in rates.multipliers.items()) + ".",
        "Tool-enabled requests add a per-model system-prompt overhead; see rates.json `tool_overhead`."]
    excluded = rates.excluded_modifiers()
    if excluded:
        lines.append("Excluded from every calculation because unverified: " + ", ".join(excluded) + ".")
    return "\n".join(lines)


def counters_series(entries: list[dict]) -> list[dict]:
    """The counters proxy: what a run cost in effort per finding, with no currency involved.

    Consumes critique-log entries. Runs with no new findings report None rather than
    dividing by zero, since 'infinite cost per finding' would be a false precision.
    Waste is carried findings over findings reconciled, counted on the same population;
    the SEV histogram counts a different one and must not be the denominator.
    Missing counter fields report None rather than raising: older logs omit some.
    """
    out = []
    for e in entries:
        c = e.get("counters")
        if not c:
            continue
        new, carried = c.get("new", 0), c.get("carried", 0)
        reconciled = new + carried
        # Absent flag means unpromoted: the protocol writes false, so optimism here would
        # under-report the one metric this series exists to drive.
        promoted = e.get("promoted", False)
        unpromoted_waste = (carried / reconciled) if reconciled and not promoted else 0.0

        def per_new(field: str):
            v = c.get(field)
            return (v / new) if (new and v is not None) else None

        out.append(
            {
                "target": e.get("t"),
                "ts": e.get("ts"),
                "calls_per_new": per_new("calls"),
                "bytes_per_new": per_new("bytes"),
                "out_chars_per_new": per_new("out_chars"),
                "budget_used": (c["calls"] / c["cap"]) if c.get("cap") and c.get("calls") is not None else None,
                "rederivation_waste": unpromoted_waste,
            }
        )
    return out


# --- Headroom proxy: measured tokens ------------------------------------------

def _get_json(url: str, timeout: float = 10.0) -> dict:
    """GET a JSON document over http(s) only; other schemes (file://) are refused."""
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError(f"only http(s) URLs are read, got {url!r}")
    with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 (scheme checked above)
        return json.loads(resp.read().decode("utf-8"))


def fetch_headroom_stats(url: str = HEADROOM_STATS_URL, timeout: float = 5.0) -> dict:
    return _get_json(url, timeout)


def _n(v) -> float:
    """Token fields may be absent or null in a proxy payload; both mean zero."""
    return float(v or 0)


def headroom_records(stats: dict, rates: Rates, site: str = "", seen: set[str] | None = None) -> list[dict]:
    """One actual per proxied request, priced by this table rather than by Headroom.

    Headroom's own dollar figures apply the 5-minute write premium to 1-hour writes, so
    only its token counts are used. Per-request input excludes cache reads and writes,
    matching Anthropic's usage.input_tokens; cache spend is logged separately by
    headroom_cache_records.
    """
    seen = set(seen or ())
    out = []
    for req in stats.get("recent_requests", []):
        rid = req.get("request_id")
        if not rid or rid in seen or req.get("error"):
            continue
        seen.add(rid)
        model = req.get("model", "")
        t_orig, t_opt, t_out = (_n(req.get("input_tokens_original")), _n(req.get("input_tokens_optimized")),
                                _n(req.get("output_tokens")))
        try:
            before = cost(rates, model, t_orig, t_out)
            after = cost(rates, model, t_opt, t_out)
        except UnknownModel as exc:
            print(f"skipped {rid}: {exc}", file=sys.stderr)
            continue
        out.append(
            {
                "site": site, "kind": "actual", "model": model, "request_id": rid,
                "request_ts": req.get("timestamp"), "in_tokens": t_opt, "in_tokens_original": t_orig,
                "out_tokens": t_out, "calls": 1, "method": "headroom /stats (per-request)",
                "via_headroom": True, "usd": round(after, 6), "usd_without_headroom": round(before, 6),
            }
        )
    return out


def _cache_snapshot(stats: dict) -> dict:
    """Cumulative cache counters since the proxy started, per model where Headroom splits them."""
    primary = stats.get("summary", {}).get("primary_model", "")
    per_model = {}
    for model, m in stats.get("cost", {}).get("per_model", {}).items():
        per_model[model] = {"w5": _n(m.get("cache_write_5m_tokens")), "w1": _n(m.get("cache_write_1h_tokens"))}
    totals = stats.get("prefix_cache", {}).get("totals", {})
    if not per_model and primary:
        per_model[primary] = {"w5": _n(totals.get("cache_write_5m_tokens")), "w1": _n(totals.get("cache_write_1h_tokens"))}
    return {
        "primary_model": primary,
        "per_model": per_model,
        "reads": _n(totals.get("cache_read_tokens")),  # not split by model in /stats
        "requests_total": _n(stats.get("requests", {}).get("total")),
    }


def headroom_cache_records(stats: dict, rates: Rates, site: str, last: dict | None) -> tuple[list[dict], dict]:
    """Cache spend since the last logged snapshot, as actuals, plus the new snapshot.

    /stats counters are cumulative for the proxy's lifetime, so only the delta is logged.
    A counter lower than last time means the proxy restarted, and the whole value is new.
    Cache reads are attributed to the primary model because /stats does not split them.
    """
    snap = _cache_snapshot(stats)
    last = last or {}
    reset = snap["requests_total"] < _n(last.get("requests_total"))
    prev_models = {} if reset else last.get("per_model", {})
    prev_reads = 0.0 if reset else _n(last.get("reads"))
    out = []
    for model, cur in snap["per_model"].items():
        prev = prev_models.get(model, {})
        d5, d1 = max(cur["w5"] - _n(prev.get("w5")), 0.0), max(cur["w1"] - _n(prev.get("w1")), 0.0)
        dr = max(snap["reads"] - prev_reads, 0.0) if model == snap["primary_model"] else 0.0
        if not (d5 or d1 or dr):
            continue
        try:
            usd = (cost(rates, model, 0, 0, cache_write_tokens=d5, cache_ttl="5m")
                   + cost(rates, model, 0, 0, cache_write_tokens=d1, cache_ttl="1h")
                   + cost(rates, model, 0, 0, cache_read_tokens=dr))
        except UnknownModel as exc:
            print(f"cache for {model} not priced: {exc}", file=sys.stderr)
            continue
        out.append({"site": site, "kind": "actual", "model": model, "method": "headroom /stats (session cache)",
                    "via_headroom": True, "cache_write_5m": d5, "cache_write_1h": d1, "cache_read": dr,
                    "calls": 0, "usd": round(usd, 6)})
    if out:
        out[-1]["cache_snapshot"] = snap
        out[-1]["requests_delta"] = requests_delta(snap, last)
    return out, snap


def requests_delta(snap: dict, last: dict | None) -> float:
    """Requests since the previous snapshot, or the whole count after a proxy restart.

    Computed once per run and stored on the one record that carries the snapshot, so a
    run with two models is counted once and a snapshot-only run still contributes.
    """
    if not last:
        return snap["requests_total"]
    prev = _n(last.get("requests_total"))
    return snap["requests_total"] if snap["requests_total"] < prev else snap["requests_total"] - prev


def last_cache_snapshot(records: list[dict]) -> dict | None:
    for r in reversed(records):
        if "cache_snapshot" in r:
            return r["cache_snapshot"]
    return None


# --- estimate versus actual ---------------------------------------------------

def is_measured(rec: dict) -> bool:
    if "kind" in rec:
        return rec["kind"] == "actual"
    return rec.get("method") in LEGACY_ACTUAL_METHODS


def pair_errors(records: list[dict]) -> dict:
    """Estimate error per estimate, in log order.

    Each estimate is paired with the actuals logged for the same site after it and before
    that site's next estimate, so a reused site label never piles old actuals onto a new
    estimate. Actuals logged before any estimate are unpaired. Error is signed: positive
    means the estimate ran high.
    """
    open_est: dict[str, dict] = {}
    pairs: list[dict] = []
    for r in records:
        site = r.get("site")
        if not site or r.get("usd") is None or r.get("kind") in SCOREBOARD_KINDS:
            continue  # a plan, shipped, realised or snapshot record never opens or feeds a pair
        if is_measured(r):
            if site in open_est:
                open_est[site]["actual"] += float(r["usd"])
                open_est[site]["n_actual"] += 1
        else:
            pair = {"site": site, "estimate_usd": float(r["usd"]), "actual": 0.0, "n_actual": 0, "ts": r.get("ts")}
            open_est[site] = pair
            pairs.append(pair)
    rows = []
    for p in pairs:
        if not p["n_actual"]:
            continue
        a = p["actual"]
        rows.append({"site": p["site"], "estimate_ts": p["ts"], "estimate_usd": p["estimate_usd"],
                     "actual_usd": round(a, 6), "actual_records": p["n_actual"],
                     "error_pct": round((p["estimate_usd"] - a) / a * 100, 1) if a else None})
    errs = [abs(r["error_pct"]) for r in rows if r["error_pct"] is not None]
    return {
        "n": len(errs),
        "mean_abs_error_pct": round(sum(errs) / len(errs), 1) if errs else None,
        "small_sample": len(errs) < 5,
        "rows": rows,
    }


# --- v2.5: savings scoreboard (plan, ship, realise, score) ----------------------

LEVERS = ("BATCH", "REPLACE", "DOWNGRADE", "CACHE", "TRIM", "PROXY")
METHODS_BY_LEVER = {
    "BATCH": ("before-after", "manual"),
    "DOWNGRADE": ("before-after", "manual"),
    "TRIM": ("before-after", "manual"),
    "CACHE": ("before-after", "headroom-cache", "manual"),
    "PROXY": ("headroom-proxy", "manual"),
    "REPLACE": ("manual",),
}
EVIDENCE_BY_METHOD = {"before-after": "measured", "headroom-proxy": "modelled-baseline",
                      "headroom-cache": "modelled-baseline"}
EVIDENCE_CLASSES = ("measured", "modelled-baseline", "estimate")  # never summed together (P3)
BILLING = ("metered", "subscription", "unknown")
UNITS = ("call", "day")
WINDOW_DAYS = 14
DEFAULT_MIN_N = 20
SCOREBOARD_KINDS = {"plan", "shipped", "realised", "snapshot"}  # none of these is an actual
LEDGER_KINDS = SCOREBOARD_KINDS - {"snapshot"}  # the scoreboard's own records; snapshots stay in windows for requests_delta


class Refusal(ValueError):
    """A scoreboard command declined to write; the log is exactly as it was."""


def parse_ts(value) -> datetime | None:
    """ISO 8601 to an aware datetime: a trailing Z becomes +00:00, a naive value is UTC.

    Raw strings are never compared. Anything that does not parse returns None so the
    caller can skip the record and count it.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    s = value.strip()
    if s[-1] in "Zz":
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def record_time(rec: dict) -> datetime | None:
    """request_ts when present (the provider's clock), otherwise ts (the logging clock)."""
    if rec.get("request_ts"):
        return parse_ts(rec["request_ts"])
    return parse_ts(rec.get("ts"))


def _now() -> datetime:
    return datetime.now().astimezone()


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def new_id(records: list[dict], prefix: str, today: date) -> str:
    """S-<yyyymmdd>-<n> for plans, R-<yyyymmdd>-<n> for realised records; n counts up per day."""
    stem = f"{prefix}-{today.strftime('%Y%m%d')}-"
    used = set()
    for r in records:
        rid = r.get("id")
        if isinstance(rid, str) and rid.startswith(stem):
            try:
                used.add(int(rid[len(stem):]))
            except ValueError:
                pass
    return f"{stem}{max(used) + 1 if used else 1}"


def _plans(records: list[dict]) -> dict[str, dict]:
    return {r["id"]: r for r in records if r.get("kind") == "plan" and r.get("id")}


def _shipped_for(records: list[dict], plan_id: str) -> dict | None:
    return next((r for r in records if r.get("kind") == "shipped" and r.get("plan_id") == plan_id), None)


def _realised_for(records: list[dict], plan_id: str) -> list[dict]:
    return [r for r in records if r.get("kind") == "realised" and r.get("plan_id") == plan_id]


def plan_record(records: list[dict], rates: Rates, *, site: str, lever: str, method: str,
                predicted_usd: float | None = None, unit: str | None = None, predicted_basis: str = "",
                baseline_model: str | None = None, after_model: str | None = None,
                agreement: float | None = None, agreement_n: int | None = None,
                billing: str = "unknown", post_hoc: bool = False, today: date | None = None) -> dict:
    """The prediction, written before the change ships (P2). Carries no usd field."""
    if not (site or "").strip():
        raise Refusal("site must be the label the actuals are logged under; a blank site would match every record")
    if lever not in LEVERS:
        raise Refusal(f"lever must be one of {', '.join(LEVERS)}, got {lever!r}")
    allowed = METHODS_BY_LEVER[lever]
    if method not in allowed:
        raise Refusal(f"method {method!r} is not listed for lever {lever}; allowed: {', '.join(allowed)}")
    if billing not in BILLING:
        raise Refusal(f"billing must be one of {', '.join(BILLING)}, got {billing!r}")
    if post_hoc:
        if predicted_usd is not None or unit is not None:
            raise Refusal("a post_hoc plan takes no predicted_usd or unit: a prediction written after the fact is not one")
    else:
        if predicted_usd is None or unit is None:
            raise Refusal("predicted_usd and unit are required unless --post-hoc")
        if unit not in UNITS:
            raise Refusal(f"unit must be one of {', '.join(UNITS)}, got {unit!r}")
        if not predicted_usd > 0:
            raise Refusal(f"predicted_usd must be positive, got {predicted_usd}")
    if lever == "DOWNGRADE":
        if not (baseline_model and after_model):
            raise Refusal("DOWNGRADE needs --baseline-model and --after-model")
        rates.rate(baseline_model)
        rates.rate(after_model)
    if (agreement is None) != (agreement_n is None):
        raise Refusal("--agreement and --agreement-n go together")
    rec = {"kind": "plan", "id": new_id(records, "S", today or date.today()), "site": site, "lever": lever,
           "method": method, "predicted_basis": predicted_basis, "billing": billing, "post_hoc": bool(post_hoc)}
    if not post_hoc:
        rec["predicted_usd"] = float(predicted_usd)
        rec["unit"] = unit
    if baseline_model:
        rec["baseline_model"] = baseline_model
    if after_model:
        rec["after_model"] = after_model
    if agreement is not None:
        rec["agreement"] = float(agreement)
        rec["agreement_n"] = int(agreement_n)
    return rec


def shipped_record(records: list[dict], plan_id: str, at: str | None = None, now: datetime | None = None) -> dict:
    """The moment the change went live. live_from is ts unless --at names an earlier real date."""
    plan = _plans(records).get(plan_id)
    if plan is None:
        raise Refusal(f"plan {plan_id} not found in the log")
    if _shipped_for(records, plan_id) is not None:
        raise Refusal(f"plan {plan_id} already has a shipped record; the log is append-only (P1)")
    now = now or _now()
    live_from = now
    if at is not None:
        at_dt = parse_ts(at)
        if at_dt is None:
            raise Refusal(f"--at {at!r} is not an ISO 8601 time")
        plan_ts = parse_ts(plan.get("ts"))
        if plan_ts is not None and at_dt < plan_ts and not plan.get("post_hoc"):
            raise Refusal(f"--at {at} is earlier than plan.ts {plan['ts']}; only a post_hoc plan ships before it was planned")
        if at_dt > now:
            raise Refusal(f"--at {at} is in the future")
        live_from = at_dt
    return {"kind": "shipped", "plan_id": plan_id, "ts": _iso(now), "live_from": live_from.isoformat()}


def _site_matches(record_site: str | None, site: str) -> bool:
    """Exact label, or a session label under it (`claude-code:2026-09-28-say-hi` under `claude-code`)."""
    rs = record_site or ""
    return rs == site or rs.startswith(site + ":")


def _window_records(records: list[dict], site: str, start: datetime, end: datetime) -> tuple[list[dict], int]:
    """Non-scoreboard records under the site with a parseable time in [start, end), and the unparseable count."""
    out, skipped = [], 0
    for r in records:
        if r.get("kind") in LEDGER_KINDS or not _site_matches(r.get("site"), site):
            continue
        t = record_time(r)
        if t is None:
            skipped += 1
            continue
        if start <= t < end:
            out.append(r)
    return out, skipped


def _reprice(rates: Rates, r: dict, model: str | None = None) -> float:
    """cost() under the current table, with cost()'s own defaults for fields a record lacks (P7)."""
    return cost(rates, model or r.get("model", ""), _n(r.get("in_tokens")), _n(r.get("out_tokens")),
                calls=int(_n(r.get("calls"))), batch=bool(r.get("batch", False)),
                cache_read_tokens=_n(r.get("cache_read")), cache_write_tokens=_n(r.get("cache_write")),
                cache_ttl=r.get("ttl") or "5m", region=r.get("region") or "global",
                tool_choice=r.get("tool_choice") or None)


def _is_cache_record(r: dict) -> bool:
    return is_measured(r) and _n(r.get("calls")) == 0 and any(k in r for k in ("cache_write_5m", "cache_write_1h", "cache_read"))


def _cache_spend(rates: Rates, r: dict) -> float:
    m = r.get("model", "")
    return (cost(rates, m, 0, 0, cache_write_tokens=_n(r.get("cache_write_5m")), cache_ttl="5m")
            + cost(rates, m, 0, 0, cache_write_tokens=_n(r.get("cache_write_1h")), cache_ttl="1h")
            + cost(rates, m, 0, 0, cache_read_tokens=_n(r.get("cache_read"))))


def _cache_net_saving(rates: Rates, r: dict) -> float:
    """Read savings against write premiums, per record; negative when the writes were not paid back."""
    m = r.get("model", "")
    rate_in, _ = rates.rate(m)
    mult = rates.multipliers
    return rate_in * (_n(r.get("cache_read")) * (1 - rates.cache_read_mult(m))
                      - _n(r.get("cache_write_5m")) * (float(mult["cache_write_5m"]) - 1)
                      - _n(r.get("cache_write_1h")) * (float(mult["cache_write_1h"]) - 1))


def _requests_in(recs: list[dict]) -> float:
    return sum(_n(r.get("requests_delta")) for r in recs if "requests_delta" in r)


def _side(rates: Rates, recs: list[dict], model: str | None = None) -> dict:
    """Priced actuals with calls > 0 on one side of a before-after comparison."""
    priced = [r for r in recs if is_measured(r) and _n(r.get("calls")) > 0]
    total = calls = tokens = 0.0
    per_call = []
    for r in priced:
        try:
            c = _reprice(rates, r, model)
        except (UnknownModel, ValueError) as exc:
            raise Refusal(f"cannot reprice a record under {r.get('site')!r} at {r.get('ts')}: {exc}") from None
        n = _n(r.get("calls"))
        total += c
        calls += n
        tokens += _n(r.get("in_tokens")) * n
        per_call.append(c / n)
    return {"n": len(priced), "calls": calls, "per_call": (total / calls) if calls else None,
            "median_per_call": median(per_call) if per_call else None,
            "tokens_per_call": (tokens / calls) if calls else None}


def _per_unit(plan: dict, realised_usd: float, units_after: float | None, days: float) -> float | None:
    unit = plan.get("unit")
    if plan.get("post_hoc") or unit is None:
        return None
    if unit == "call":
        return realised_usd / units_after if units_after else None
    return realised_usd / days if days else None


def _days(start: datetime, end: datetime) -> float:
    return round((end - start).total_seconds() / 86400, 3)


def _realise_manual(plan: dict, live_from: datetime, until: datetime, realised_usd, basis, calls_replaced, evidence) -> dict:
    if realised_usd is None or not basis:
        raise Refusal("manual realise needs --realised-usd and --basis")
    default = "modelled-baseline" if calls_replaced is not None else "estimate"
    if evidence is not None:
        if evidence == "measured":
            raise Refusal("manual evidence is never measured: measured means priced actuals on both sides of the change")
        if evidence not in EVIDENCE_CLASSES:
            raise Refusal(f"evidence must be one of {', '.join(EVIDENCE_CLASSES)}, got {evidence!r}")
        if EVIDENCE_CLASSES.index(evidence) < EVIDENCE_CLASSES.index(default):
            raise Refusal(f"--evidence {evidence} would raise the class above {default}; it may only lower it")
    if plan.get("unit") == "call" and calls_replaced is None:
        raise Refusal("manual realise with unit 'call' needs --calls-replaced, counted from the application's own logs")
    days = _days(live_from, until)
    body = {"realised_usd": float(realised_usd),
            "realised_per_unit": _per_unit(plan, float(realised_usd), calls_replaced, days),
            "realised_basis": basis, "evidence": evidence or default,
            "window_start": _iso(live_from), "window_end": _iso(until), "days": days,
            "n_before": 0, "n_after": int(calls_replaced) if calls_replaced is not None else 0,
            "tokens_per_call_before": None, "tokens_per_call_after": None, "skipped_times": 0}
    if calls_replaced is not None:
        body["calls_replaced"] = int(calls_replaced)
    return body


def _realise_before_after(records, rates, plan, live_from, until, min_n) -> dict:
    window = timedelta(days=WINDOW_DAYS)
    end = min(live_from + window, until)
    before, skipped = _window_records(records, plan["site"], live_from - window, live_from)
    after, _ = _window_records(records, plan["site"], live_from, end)
    b = _side(rates, before, plan.get("baseline_model") if plan["lever"] == "DOWNGRADE" else None)
    a = _side(rates, after)
    for name, side in (("before", b), ("after", a)):
        if side["n"] < min_n:
            raise Refusal(f"{name} window holds {side['n']} record(s) with calls > 0, fewer than --min-n {min_n}")
    realised = (b["per_call"] - a["per_call"]) * a["calls"]
    days = _days(live_from, end)
    return {"realised_usd": round(realised, 6), "realised_per_unit": _per_unit(plan, realised, a["calls"], days),
            "evidence": "measured", "window_start": _iso(live_from - window), "window_end": _iso(end), "days": days,
            "n_before": b["n"], "n_after": a["n"], "calls_before": b["calls"], "calls_after": a["calls"],
            "per_call_before": b["per_call"], "per_call_after": a["per_call"],
            "median_per_call_before": b["median_per_call"], "median_per_call_after": a["median_per_call"],
            "tokens_per_call_before": b["tokens_per_call"], "tokens_per_call_after": a["tokens_per_call"],
            "skipped_times": skipped}


def _cache_per_request(rates: Rates, recs: list[dict], fn) -> tuple[float | None, float, int]:
    cache = [r for r in recs if _is_cache_record(r)]
    req = _requests_in(recs)
    amount = sum(fn(rates, r) for r in cache)
    return ((amount / req) if req else None), req, len(cache)


def _realise_headroom_proxy(records, rates, plan, live_from, until) -> dict:
    window = timedelta(days=WINDOW_DAYS)
    after, skipped = _window_records(records, plan["site"], live_from, until)  # no cap: rescored to date
    before, _ = _window_records(records, plan["site"], live_from - window, live_from)
    reqs = [r for r in after if is_measured(r) and r.get("in_tokens_original") is not None and _n(r.get("calls")) > 0]
    saving = 0.0
    for r in reqs:
        try:
            saving += (cost(rates, r.get("model", ""), _n(r.get("in_tokens_original")), _n(r.get("out_tokens")))
                       - cost(rates, r.get("model", ""), _n(r.get("in_tokens")), _n(r.get("out_tokens"))))
        except (UnknownModel, ValueError) as exc:
            raise Refusal(f"cannot reprice request {r.get('request_id')}: {exc}") from None
    cb, _, nb = _cache_per_request(rates, before, _cache_spend)
    ca, _, na = _cache_per_request(rates, after, _cache_spend)
    flags = []
    if nb == 0:
        flags.append("NO BEFORE DATA")
    elif (nb and cb is None) or (na and ca is None):
        flags.append("NO REQUEST COUNT")  # cache records from before v2.5 carry no requests_delta
    elif ca is not None and cb is not None and ca > cb:
        flags.append("CACHE COST ROSE")
    days = _days(live_from, until)
    try:
        b = _side(rates, before)  # context only: the proxy saving uses no before side
    except Refusal:
        b = {"n": 0, "tokens_per_call": None}
    return {"realised_usd": round(saving, 6), "realised_per_unit": _per_unit(plan, saving, len(reqs), days),
            "evidence": "modelled-baseline", "window_start": _iso(live_from), "window_end": _iso(until), "days": days,
            "n_before": b["n"], "n_after": len(reqs),
            "tokens_per_call_before": b["tokens_per_call"],
            "tokens_per_call_after": (sum(_n(r.get("in_tokens")) for r in reqs) / len(reqs)) if reqs else None,
            "tokens_saved": sum(_n(r.get("in_tokens_original")) - _n(r.get("in_tokens")) for r in reqs),
            "cache_per_request_before": cb, "cache_per_request_after": ca,
            "cache_records_before": nb, "cache_records_after": na, "flags": flags, "skipped_times": skipped}


def _realise_headroom_cache(records, rates, plan, live_from, until, min_n) -> dict:
    window = timedelta(days=WINDOW_DAYS)
    end = min(live_from + window, until)
    before, skipped = _window_records(records, plan["site"], live_from - window, live_from)
    after, _ = _window_records(records, plan["site"], live_from, end)
    try:
        pb, req_b, nb = _cache_per_request(rates, before, _cache_net_saving)
        pa, req_a, na = _cache_per_request(rates, after, _cache_net_saving)
    except (UnknownModel, ValueError) as exc:
        raise Refusal(f"cannot price a cache record: {exc}") from None
    for name, req in (("before", req_b), ("after", req_a)):
        if req < min_n:
            raise Refusal(f"{name} window holds {req:.0f} request(s) (sum of requests_delta), fewer than --min-n {min_n}")
    realised = (pa - pb) * req_a
    days = _days(live_from, end)
    return {"realised_usd": round(realised, 8), "realised_per_unit": _per_unit(plan, realised, req_a, days),
            "evidence": "modelled-baseline", "window_start": _iso(live_from - window), "window_end": _iso(end),
            "days": days, "n_before": int(req_b), "n_after": int(req_a),
            "net_per_request_before": pb, "net_per_request_after": pa,
            "cache_records_before": nb, "cache_records_after": na,
            "tokens_per_call_before": None, "tokens_per_call_after": None, "skipped_times": skipped}


def realise_record(records: list[dict], rates: Rates, plan_id: str, *, auto: bool = False, until: str | None = None,
                   min_n: int = DEFAULT_MIN_N, supersede: str | None = None, lesson: str | None = None,
                   realised_usd: float | None = None, basis: str | None = None, calls_replaced: int | None = None,
                   evidence: str | None = None, now: datetime | None = None) -> dict:
    """Score a shipped plan over its window. A second scoring names the first with `supersedes`."""
    now = now or _now()
    plan = _plans(records).get(plan_id)
    if plan is None:
        raise Refusal(f"plan {plan_id} not found in the log")
    shipped = _shipped_for(records, plan_id)
    if shipped is None:
        raise Refusal(f"plan {plan_id} has no shipped record; run ship first")
    plan_ts, ship_ts = parse_ts(plan.get("ts")), parse_ts(shipped.get("ts"))
    if plan_ts and ship_ts and plan_ts > ship_ts:
        raise Refusal(f"plan.ts {plan['ts']} is later than shipped.ts {shipped['ts']} (P2): "
                      f"the prediction was not written before the change shipped")
    earlier = _realised_for(records, plan_id)
    newest = earlier[-1].get("id") if earlier else None
    if earlier and supersede is None:
        raise Refusal(f"plan {plan_id} already has realised record {newest}; pass --supersede {newest} to rescore")
    if supersede is not None and supersede != newest:
        raise Refusal(f"--supersede {supersede} is not the newest realised record for plan {plan_id} "
                      f"({newest or 'none exists'})")
    live_from = parse_ts(shipped.get("live_from")) or ship_ts
    if live_from is None:
        raise Refusal(f"shipped record for {plan_id} has no parseable live_from")
    until_dt = parse_ts(until) if until else now
    if until_dt is None:
        raise Refusal(f"--until {until!r} is not an ISO 8601 time")
    if until_dt <= live_from:
        raise Refusal(f"--until {until_dt.isoformat()} is not after live_from {live_from.isoformat()}")
    method = plan.get("method")
    if method == "manual":
        if auto:
            raise Refusal("a manual plan is realised with --realised-usd and --basis, not --auto")
        body = _realise_manual(plan, live_from, until_dt, realised_usd, basis, calls_replaced, evidence)
    elif not auto:
        raise Refusal(f"method {method!r} is realised with --auto")
    elif method == "before-after":
        body = _realise_before_after(records, rates, plan, live_from, until_dt, min_n)
    elif method == "headroom-proxy":
        body = _realise_headroom_proxy(records, rates, plan, live_from, until_dt)
    elif method == "headroom-cache":
        body = _realise_headroom_cache(records, rates, plan, live_from, until_dt, min_n)
    else:
        raise Refusal(f"plan {plan_id} has an unknown method {method!r}")
    rec = {"kind": "realised", "id": new_id(records, "R", now.date()), "plan_id": plan_id, "method": method,
           "ts": _iso(now)}
    rec.update(body)
    if supersede:
        rec["supersedes"] = supersede
    if lesson:
        rec["lesson"] = lesson
    return rec


def score_report(records: list[dict], *, since: str | None = None, site: str | None = None,
                 lever: str | None = None) -> dict:
    """The scoreboard as data. Only the newest realised record per plan counts."""
    plans = _plans(records)
    shipped_ids = {r.get("plan_id") for r in records if r.get("kind") == "shipped"}
    newest: dict[str, dict] = {}
    superseded: list[str] = []
    for r in records:
        if r.get("kind") != "realised":
            continue
        pid = r.get("plan_id")
        if pid in newest:
            superseded.append(newest[pid].get("id"))
        newest[pid] = r
    since_dt = parse_ts(since) if since else None
    if since and since_dt is None:
        raise Refusal(f"--since {since!r} is not a date")
    rows = []
    for pid, r in newest.items():
        p = plans.get(pid)
        if p is None:
            continue
        if site and not _site_matches(p.get("site"), site):
            continue
        if lever and p.get("lever") != lever:
            continue
        if since_dt and (parse_ts(r.get("ts")) or since_dt) < since_dt:
            continue
        rows.append((p, r))

    by: dict[tuple, dict] = {}
    for p, r in rows:
        key = (p["lever"], p.get("billing", "unknown"))
        cell = by.setdefault(key, {"lever": key[0], "billing": key[1], "list_price": key[1] != "metered",
                                   **{e: {"usd": 0.0, "n": 0} for e in EVIDENCE_CLASSES}})
        ev = r.get("evidence") if r.get("evidence") in EVIDENCE_CLASSES else "estimate"
        cell[ev]["usd"] = round(cell[ev]["usd"] + float(r.get("realised_usd") or 0.0), 6)
        cell[ev]["n"] += 1

    groups: dict[tuple, list] = {}
    for p, r in rows:
        ev, rpu, pred = r.get("evidence"), r.get("realised_per_unit"), p.get("predicted_usd")
        if p.get("post_hoc") or ev not in ("measured", "modelled-baseline") or rpu is None or not pred:
            continue
        groups.setdefault((p["lever"], ev), []).append((float(rpu), float(pred)))
    accuracy = []
    for (lv, ev), pairs in groups.items():
        ratios = [a / b for a, b in pairs]
        apes = [abs(a - b) / b * 100 for a, b in pairs]
        accuracy.append({"lever": lv, "evidence": ev, "n": len(pairs), "median_ratio": round(median(ratios), 3),
                         "mape_pct": round(sum(apes) / len(apes), 1), "small_sample": len(pairs) < 5})

    zero = [{"plan_id": p["id"], "lever": p["lever"], "site": p.get("site"), "realised_usd": r.get("realised_usd"),
             "lesson": r.get("lesson")} for p, r in rows if float(r.get("realised_usd") or 0.0) <= 0]
    unaudited = [{"plan_id": p["id"], "site": p.get("site"), "realised_usd": r.get("realised_usd")}
                 for p, r in rows if p["lever"] == "REPLACE" and p.get("agreement") is None]
    lessons = sorted(({"ts": r.get("ts"), "plan_id": p["id"], "lever": p["lever"], "lesson": r["lesson"]}
                      for p, r in rows if r.get("lesson")), key=lambda x: x["ts"] or "", reverse=True)[:10]
    skipped = sum(1 for r in records if r.get("kind") not in LEDGER_KINDS and record_time(r) is None)
    header = {"plans": len(plans),
              "billing_mix": {b: sum(1 for p in plans.values() if p.get("billing", "unknown") == b) for b in BILLING},
              "unshipped": [pid for pid in plans if pid not in shipped_ids],
              "unrealised": [pid for pid in plans if pid in shipped_ids and pid not in newest],
              "skipped_times": skipped}
    return {"header": header, "by_lever": list(by.values()), "accuracy": accuracy, "zero_or_negative": zero,
            "unaudited_replace": unaudited, "lessons": lessons, "superseded": superseded}


def format_score(res: dict, log_path: Path, rates_verified: str) -> str:
    h = res["header"]
    mix = ", ".join(f"{k} {v}" for k, v in h["billing_mix"].items())
    lines = [f"token-aware score | log {log_path} | rates verified {rates_verified} | plans {h['plans']} ({mix})",
             f"not yet shipped: {', '.join(h['unshipped']) or 'none'} | shipped, not yet realised: "
             f"{', '.join(h['unrealised']) or 'none'} | records skipped for an unparseable time: {h['skipped_times']}"]
    if res["superseded"]:
        lines.append("superseded realised records: " + ", ".join(str(s) for s in res["superseded"]))
    lines += ["", "savings by lever and billing, USD (n); evidence classes are never summed across columns",
              f"  {'lever':<10}{'billing':<14}{'':<12}{'measured':<20}{'modelled-baseline':<20}{'estimate':<20}"]
    for row in res["by_lever"]:
        cells = [f"{row[e]['usd']:.6f} ({row[e]['n']})" if row[e]["n"] else "-" for e in EVIDENCE_CLASSES]
        tag = "list-price" if row["list_price"] else ""
        lines.append(f"  {row['lever']:<10}{row['billing']:<14}{tag:<12}" + "".join(f"{c:<20}" for c in cells))
    lines += ["", "prediction accuracy per unit (median realised/predicted, MAPE); post_hoc plans excluded"]
    for a in res["accuracy"] or []:
        flag = "  small sample" if a["small_sample"] else ""
        lines.append(f"  {a['lever']:<10}{a['evidence']:<20}n={a['n']:<4}median {a['median_ratio']:.3f}  "
                     f"MAPE {a['mape_pct']:.1f}%{flag}")
    if not res["accuracy"]:
        lines.append("  none yet")
    lines += ["", "zero-or-negative savings"]
    lines += [f"  {z['plan_id']}  {z['lever']}  {z['site']}  {z['realised_usd']}  {z['lesson'] or ''}".rstrip()
              for z in res["zero_or_negative"]] or ["  none"]
    lines += ["", "REPLACE with no agreement rate: unaudited"]
    lines += [f"  {u['plan_id']}  {u['site']}  {u['realised_usd']}" for u in res["unaudited_replace"]] or ["  none"]
    lines += ["", "lessons, newest first"]
    lines += [f"  {(l['ts'] or '')[:10]}  {l['plan_id']}  {l['lesson']}" for l in res["lessons"]] or ["  none"]
    return "\n".join(lines)


# --- drift check against a secondary price source ------------------------------

_LITELLM_FIELDS = {"in": "input_cost_per_token", "out": "output_cost_per_token"}


def price_drift(rates: Rates, prices: dict) -> dict:
    """Compare rates.json with LiteLLM's community map (a secondary source).

    A disagreement means one of the two is stale: re-read the first-party page before
    changing anything, since this map is community-maintained. Models absent from the map
    are reported, never treated as agreement.
    """
    diffs, missing, agree = [], [], []
    for model, m in rates.models.items():
        entry = prices.get(model) or prices.get(f"anthropic/{model}")
        if not entry:
            missing.append(model)
            continue
        ok = True
        for k, field in _LITELLM_FIELDS.items():
            theirs = entry.get(field)
            if theirs is None:
                continue
            if abs(float(theirs) * 1e6 - float(m[k])) > 1e-6:
                diffs.append({"model": model, "field": k, "rates_json": m[k], "litellm": round(float(theirs) * 1e6, 6)})
                ok = False
        read = entry.get("cache_read_input_token_cost")
        if read is not None and abs(float(read) * 1e6 - m["in"] * rates.cache_read_mult(model)) > 1e-6:
            diffs.append({"model": model, "field": "cache_read", "rates_json": round(m["in"] * rates.cache_read_mult(model), 6),
                          "litellm": round(float(read) * 1e6, 6)})
            ok = False
        if ok:
            agree.append(model)
    return {"diffs": diffs, "missing": missing, "agree": agree}


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("cost", help="modelled cost for a call site")
    c.add_argument("--model", required=True)
    c.add_argument("--in", dest="in_tokens", type=float, required=True)
    c.add_argument("--out", dest="out_tokens", type=float, required=True)
    c.add_argument("--calls", type=int, default=1)
    c.add_argument("--batch", action="store_true")
    c.add_argument("--cache-read", type=float, default=0.0)
    c.add_argument("--cache-write", type=float, default=0.0)
    c.add_argument("--ttl", default="5m", choices=["5m", "1h"])
    c.add_argument("--region", default="global", choices=["global", "us"])
    c.add_argument("--tool-choice", default=None, choices=["auto", "none", "any", "tool"],
                   help="adds that model's tool-use system prompt overhead")
    c.add_argument("--method", default="estimated", help="how the token counts were obtained")
    c.add_argument("--site", default="", help="file::function or session label this figure belongs to")
    c.add_argument("--via-headroom", action="store_true", help="the call ran through the Headroom proxy")
    c.add_argument("--actual", action="store_true",
                   help="token counts are measured (provider usage, ccusage), not estimated; logs kind=actual")
    c.add_argument("--log", action="store_true", help="append to cost_log.jsonl")

    b = sub.add_parser("breakeven", help="re-reads needed before caching pays")
    b.add_argument("--ttl", default="5m", choices=["5m", "1h"])
    b.add_argument("--model", default=None, help="use that model's cache-read multiplier")

    p = sub.add_parser("compare", help="rate ratio between two models")
    p.add_argument("--a", required=True)
    p.add_argument("--b", required=True)

    e = sub.add_parser("estimate", help="over-estimate tokens in a file")
    e.add_argument("path")
    e.add_argument("--code", action="store_true")
    e.add_argument("--model", default=None, help="use that model's tokenizer factor")

    sub.add_parser("verify", help="logged figures computed against a since-expired table")
    sub.add_parser("render", help="emit the pricing.md snapshot")

    d = sub.add_parser("cpd", help="counters proxy series from a critique log")
    d.add_argument("log", help="path to a critique-log jsonl file")

    h = sub.add_parser("headroom", help="price the requests a Headroom proxy has seen")
    src = h.add_mutually_exclusive_group()
    src.add_argument("--url", default=HEADROOM_STATS_URL)
    src.add_argument("--file", default=None, help="a saved /stats JSON instead of the live endpoint")
    h.add_argument("--site", default="", help="session label, to pair with an estimate; required with --log")
    h.add_argument("--log", action="store_true", help="append new requests and cache spend to the log")

    sub.add_parser("pairs", help="estimate error where a site has both an estimate and an actual")

    k = sub.add_parser("check", help="flag drift between rates.json and LiteLLM's community price map")
    k.add_argument("--url", default=LITELLM_PRICES_URL)
    k.add_argument("--file", default=None, help="a saved copy of the price map instead of the live URL")

    pl = sub.add_parser("plan", help="record a predicted saving before the change ships")
    pl.add_argument("--site", required=True, help="the call-site label its actuals are logged under")
    pl.add_argument("--lever", required=True, choices=LEVERS)
    pl.add_argument("--method", required=True, help="before-after, headroom-proxy, headroom-cache or manual")
    pl.add_argument("--predicted-usd", dest="predicted_usd", type=float, default=None)
    pl.add_argument("--unit", default=None, choices=UNITS)
    pl.add_argument("--basis", dest="predicted_basis", default="", help="one line on where the prediction came from")
    pl.add_argument("--baseline-model", dest="baseline_model", default=None)
    pl.add_argument("--after-model", dest="after_model", default=None)
    pl.add_argument("--agreement", type=float, default=None, help="REPLACE agreement rate, 0 to 1")
    pl.add_argument("--agreement-n", dest="agreement_n", type=int, default=None)
    pl.add_argument("--billing", default="unknown", choices=BILLING)
    pl.add_argument("--post-hoc", dest="post_hoc", action="store_true",
                    help="the change was live before this plan; scored but outside prediction accuracy")

    sh = sub.add_parser("ship", help="record that a planned change went live")
    sh.add_argument("--id", dest="plan_id", required=True)
    sh.add_argument("--at", default=None, help="ISO time of the real go-live when earlier than now")

    rl = sub.add_parser("realise", help="score a shipped plan over its window")
    rl.add_argument("--id", dest="plan_id", required=True)
    rl.add_argument("--auto", action="store_true", help="compute from the log (before-after, headroom-*)")
    rl.add_argument("--until", default=None, help="ISO end of the after window; default now")
    rl.add_argument("--min-n", dest="min_n", type=int, default=DEFAULT_MIN_N)
    rl.add_argument("--supersede", default=None, help="id of the realised record this one replaces")
    rl.add_argument("--lesson", default=None, help="one line, searchable with kb-search")
    rl.add_argument("--realised-usd", dest="realised_usd", type=float, default=None, help="manual: the figure")
    rl.add_argument("--basis", dest="realised_basis", default=None, help="manual: where the figure came from")
    rl.add_argument("--calls-replaced", dest="calls_replaced", type=int, default=None,
                    help="manual: calls replaced, from the application's own logs")
    rl.add_argument("--evidence", default=None, choices=EVIDENCE_CLASSES, help="manual: may only lower the class")

    sc = sub.add_parser("score", help="savings by lever, prediction accuracy, lessons")
    sc.add_argument("--since", default=None, help="YYYY-MM-DD; realised records from this date")
    sc.add_argument("--site", default=None)
    sc.add_argument("--lever", default=None, choices=LEVERS)
    sc.add_argument("--json", dest="as_json", action="store_true")
    sc.add_argument("--out", default=None, help="write UTF-8 without a BOM (a PowerShell 5.1 > redirect writes UTF-16)")

    a = ap.parse_args(argv)

    if a.cmd == "cpd":
        for row in counters_series(_read_jsonl(Path(a.log))):
            print(json.dumps(row, ensure_ascii=False))
        return 0

    if a.cmd == "pairs":
        path = LOG_PATH
        res = pair_errors(_read_jsonl(path) if path.exists() else [])
        label = " (small sample)" if res["small_sample"] else ""
        print(f"n={res['n']} paired site(s){label}; mean absolute error "
              f"{res['mean_abs_error_pct'] if res['mean_abs_error_pct'] is not None else 'n/a'}%")
        for row in res["rows"]:
            print(json.dumps(row, ensure_ascii=False))
        return 0

    if a.cmd == "estimate" and a.model is None:
        text = Path(a.path).read_text(encoding="utf-8")
        print(f"{estimate_tokens(text, a.code)} tokens (estimate, chars/{'code' if a.code else 'prose'} basis, "
              f"tokenizer factor {NEWER_TOKENIZER_FACTOR})")
        return 0

    if a.cmd == "score":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
        try:
            res = score_report(_read_jsonl(LOG_PATH) if LOG_PATH.exists() else [],
                               since=a.since, site=a.site, lever=a.lever)
        except Refusal as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 2
        verified = json.loads(RATES_PATH.read_text(encoding="utf-8")).get("verified", "?") if RATES_PATH.exists() else "?"
        text = json.dumps(res, ensure_ascii=False, indent=1) if a.as_json else format_score(res, LOG_PATH, verified)
        if a.out:
            Path(a.out).write_text(text + "\n", encoding="utf-8")
            print(f"wrote {a.out}")
        else:
            print(text)
        return 0

    try:
        rates = load_rates()
    except RatesExpired as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2

    if a.cmd in ("plan", "ship", "realise"):
        records = _read_jsonl(LOG_PATH) if LOG_PATH.exists() else []
        try:
            if a.cmd == "plan":
                rec = plan_record(records, rates, site=a.site, lever=a.lever, method=a.method,
                                  predicted_usd=a.predicted_usd, unit=a.unit, predicted_basis=a.predicted_basis,
                                  baseline_model=a.baseline_model, after_model=a.after_model,
                                  agreement=a.agreement, agreement_n=a.agreement_n, billing=a.billing,
                                  post_hoc=a.post_hoc)
            elif a.cmd == "ship":
                rec = shipped_record(records, a.plan_id, at=a.at)
            else:
                rec = realise_record(records, rates, a.plan_id, auto=a.auto, until=a.until, min_n=a.min_n,
                                     supersede=a.supersede, lesson=a.lesson, realised_usd=a.realised_usd,
                                     basis=a.realised_basis, calls_replaced=a.calls_replaced, evidence=a.evidence)
        except (Refusal, UnknownModel) as exc:
            print(f"refused: {exc}", file=sys.stderr)
            return 2
        rec = log_record(rates, rec)
        if a.cmd == "realise":
            flags = " ".join(rec.get("flags") or [])
            print(f"{rec['id']} {rec['plan_id']} {rec['method']} {rec['evidence']}: realised {rec['realised_usd']} USD"
                  f" over {rec['days']} day(s), n_before {rec['n_before']}, n_after {rec['n_after']},"
                  f" per unit {rec['realised_per_unit']}; {rec.get('skipped_times', 0)} record(s) skipped for an"
                  f" unparseable time" + (f"; {flags}" if flags else ""))
            if rec.get("cache_per_request_before") is not None or rec.get("cache_per_request_after") is not None:
                print(f"cache spend per request: before {rec.get('cache_per_request_before')}, "
                      f"after {rec.get('cache_per_request_after')}")
        else:
            print(json.dumps(rec, ensure_ascii=False))
        return 0

    if a.cmd == "estimate":
        text = Path(a.path).read_text(encoding="utf-8")
        f = rates.tokenizer_factor(a.model)
        print(f"{estimate_tokens(text, a.code, f)} tokens (estimate, chars/{'code' if a.code else 'prose'} basis, "
              f"tokenizer factor {f} for {a.model})")
        return 0

    if a.cmd == "cost":
        try:
            usd = cost(rates, a.model, a.in_tokens, a.out_tokens, a.calls, a.batch,
                       a.cache_read, a.cache_write, a.ttl, a.region, a.tool_choice)
        except (UnknownModel, ValueError) as exc:
            print(f"not priced: {exc}", file=sys.stderr)
            return 2
        print(f"${usd:.6f}  ({a.calls} call(s), rates verified {rates.verified})")
        if rates.excluded_modifiers():
            print("excluded, unverified: " + ", ".join(rates.excluded_modifiers()))
        if a.log:
            log_record(rates, {"site": a.site, "model": a.model, "in_tokens": a.in_tokens,
                               "out_tokens": a.out_tokens, "calls": a.calls, "batch": a.batch,
                               "cache_read": a.cache_read, "cache_write": a.cache_write, "ttl": a.ttl,
                               "region": a.region, "tool_choice": a.tool_choice,
                               "via_headroom": a.via_headroom, "method": a.method,
                               "kind": "actual" if a.actual else "estimate", "usd": round(usd, 6)})
        return 0

    if a.cmd == "breakeven":
        print(f"{cache_breakeven_reads(rates, a.ttl, a.model)} re-read(s) on the {a.ttl} tier"
              + (f" for {a.model}" if a.model else ""))
        return 0

    if a.cmd == "compare":
        r = compare(rates, a.a, a.b)
        print(f"{a.a} vs {a.b}: input {r['in_ratio']:.2f}x, output {r['out_ratio']:.2f}x")
        return 0

    if a.cmd == "render":
        print(render_table(rates))
        return 0

    if a.cmd == "verify":
        stale = verify_log()
        print(f"{len(stale)} figure(s) computed against a since-expired table")
        for rec in stale:
            print(f"  {rec.get('ts')}  {rec.get('site') or rec.get('model')}  table {rec.get('rates_verified')}")
        return 0

    if a.cmd == "headroom":
        if a.log and not a.site:
            print("--log needs --site, so the records can be paired with an estimate", file=sys.stderr)
            return 2
        try:
            stats = (json.loads(Path(a.file).read_text(encoding="utf-8")) if a.file
                     else fetch_headroom_stats(a.url))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            print(f"could not read Headroom stats: {exc}", file=sys.stderr)
            return 2
        existing = _read_jsonl(LOG_PATH) if LOG_PATH.exists() else []
        seen = {r.get("request_id") for r in existing if r.get("request_id")}
        recs = headroom_records(stats, rates, a.site, seen)
        last = last_cache_snapshot(existing)
        cache_recs, snap = headroom_cache_records(stats, rates, a.site, last)
        saved = sum(r["in_tokens_original"] - r["in_tokens"] for r in recs)
        print(f"{len(recs)} new request(s); input tokens saved {saved:.0f}; USD {sum(r['usd'] for r in recs):.6f} "
              f"with the proxy, {sum(r['usd_without_headroom'] for r in recs):.6f} without")
        for r in cache_recs:
            print(f"cache since last run ({r['model']}): 5m writes {r['cache_write_5m']:.0f}, 1h writes "
                  f"{r['cache_write_1h']:.0f}, reads {r['cache_read']:.0f} -> ${r['usd']:.6f}")
        prev_total = 0.0 if (last is None or snap["requests_total"] < _n(last.get("requests_total"))) \
            else _n(last.get("requests_total"))
        missed = snap["requests_total"] - prev_total - len(recs)
        if last is not None and missed > 0:
            print(f"WARNING: {missed:.0f} request(s) since the last run are not in recent_requests "
                  f"(errored or rotated out); run this after every session.", file=sys.stderr)
        if a.log:
            for r in recs + cache_recs:
                log_record(rates, r)
            if not cache_recs:  # keep the snapshot current even when nothing new was cached
                log_record(rates, {"site": a.site, "kind": "snapshot", "method": "headroom /stats (snapshot)",
                                   "cache_snapshot": snap, "requests_delta": requests_delta(snap, last)})
        return 0

    if a.cmd == "check":
        try:
            prices = (json.loads(Path(a.file).read_text(encoding="utf-8")) if a.file else _get_json(a.url, 30.0))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            print(f"could not read the price map: {exc}", file=sys.stderr)
            return 2
        res = price_drift(rates, prices)
        print(f"agree: {', '.join(res['agree']) or 'none'}")
        print(f"not in the map (check by hand): {', '.join(res['missing']) or 'none'}")
        for d in res["diffs"]:
            print(f"DRIFT {d['model']} {d['field']}: rates.json {d['rates_json']} vs LiteLLM {d['litellm']}")
        if res["diffs"]:
            print("Re-read the first-party pricing page before changing rates.json; the map is secondary.")
        return 1 if res["diffs"] else 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

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

Subcommands: cost, breakeven, compare, estimate, verify, render, cpd, headroom, pairs, check.
Python 3.10+, standard library only, so it runs on 3.10, 3.12 and 3.13 alike.
Version 2.3 (2026-09-28).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
RATES_PATH = HERE / "rates.json"
# The log holds private usage records. TOKEN_AWARE_LOG moves it out of the skill folder
# (for example to <project>/.claude/token-aware/cost_log.jsonl) so it never ships with the skill.
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
        ts=datetime.now().astimezone().isoformat(timespec="seconds"),
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
    return out, snap


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
        if not site or r.get("usd") is None:
            continue
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

    rates = load_rates()

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
                                   "cache_snapshot": snap})
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

"""Cost arithmetic for the token-aware skill.

Deterministic arithmetic belongs in Python, not in prose: this module exists because a
break-even claim written by hand contradicted the multipliers printed beside it.

Canonical rates live in rates.json. Nothing here reaches the network, and no figure is
returned from an expired table. Every computed figure can be appended to cost_log.jsonl
with the rate-table date and the token-count method, so it can be recomputed later.

Subcommands: cost, breakeven, compare, estimate, verify, render, cpd.
Python 3.10+, standard library only.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
RATES_PATH = HERE / "rates.json"
LOG_PATH = HERE / "cost_log.jsonl"

WARN_WINDOW_DAYS = 7
CHARS_PER_TOKEN_PROSE = 3.5
CHARS_PER_TOKEN_CODE = 2.5
BUDGET_SAFETY = 0.8  # shrinks chars/token, so estimates run high


class RatesExpired(RuntimeError):
    """Raised when the rate table is past its expiry; a stale figure must not reach a report."""


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

    def rate(self, model: str) -> tuple[float, float]:
        try:
            m = self.models[model]
        except KeyError:
            raise UnknownModel(
                f"{model!r} is not in rates.json. Add it with a verified date rather than assuming a rate."
            ) from None
        return float(m["in"]) / 1e6, float(m["out"]) / 1e6

    def excluded_modifiers(self) -> list[str]:
        """Null modifiers are excluded from every calculation and named in the output."""
        return sorted(k for k, v in self.modifiers.items() if v is None)

    def secondary_facts(self) -> list[str]:
        return sorted(k for k, v in self.provenance.items() if v.get("class") in ("secondary", "unverified"))


def load_rates(path: Path | None = None, today: date | None = None) -> Rates:
    """Load the table, warning inside the expiry window and refusing past it.

    path defaults to the module-level RATES_PATH, resolved at call time rather than at
    import time, so overriding cost.RATES_PATH (directly or via monkeypatch) takes effect.
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
) -> float:
    """Modelled cost in USD for `calls` identical calls.

    in_tokens counts uncached input only; cached input is passed separately so the
    multipliers apply where they actually apply. Output always bills at full rate.
    """
    _check_non_negative(
        in_tokens=in_tokens, out_tokens=out_tokens, cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
    )
    if calls < 0:
        raise ValueError(f"calls must be non-negative, got {calls}")
    if cache_ttl not in ("5m", "1h"):
        raise ValueError("cache_ttl must be '5m' or '1h'")
    rate_in, rate_out = rates.rate(model)
    write_mult = rates.multipliers["cache_write_5m"] if cache_ttl == "5m" else rates.multipliers["cache_write_1h"]
    per_call = (
        in_tokens * rate_in
        + cache_read_tokens * rate_in * rates.multipliers["cache_read"]
        + cache_write_tokens * rate_in * write_mult
        + out_tokens * rate_out
    )
    if batch:
        per_call *= rates.multipliers["batch"]
    return per_call * calls


def cache_breakeven_reads(rates: Rates, ttl: str = "5m") -> int:
    """Smallest number of re-reads after the write at which caching is cheaper.

    Compares n+1 uncached sends against one write plus n reads, on the cached prefix only.
    """
    write = rates.multipliers["cache_write_5m"] if ttl == "5m" else rates.multipliers["cache_write_1h"]
    read = rates.multipliers["cache_read"]
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


def estimate_tokens(text: str, code: bool = False) -> int:
    """Deliberate over-estimate for budgeting only, never a billing figure."""
    base = CHARS_PER_TOKEN_CODE if code else CHARS_PER_TOKEN_PROSE
    return int(len(text) / (base * BUDGET_SAFETY))


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
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        exp = rec.get("rates_expires")
        if exp and date.fromisoformat(exp) < today:
            stale.append(rec)
    return stale


def render_table(rates: Rates) -> str:
    """The pricing.md snapshot. Generated, so the copy cannot drift from the canonical table."""
    lines = [
        f"<!-- generated by: python tools/cost.py render | verified {rates.verified} | expires {rates.expires} -->",
        "",
        "| Model | Input | Output | Min cacheable |",
        "|---|---|---|---|",
    ]
    for name, m in rates.models.items():
        mc = m.get("cache_min_tokens")
        lines.append(
            f"| `{name}` | ${m['in']:.2f} | ${m['out']:.2f} | {mc if mc is not None else 'not measured'} |"
        )
    lines += ["", f"Source: {rates.source}. Multipliers: " + ", ".join(
        f"{k} {v}x" for k, v in rates.multipliers.items()) + "."]
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
        out.append(
            {
                "target": e.get("t"),
                "ts": e.get("ts"),
                "calls_per_new": (c["calls"] / new) if new else None,
                "bytes_per_new": (c["bytes"] / new) if new else None,
                "out_chars_per_new": (c["out_chars"] / new) if new else None,
                "budget_used": (c["calls"] / c["cap"]) if c.get("cap") else None,
                "rederivation_waste": unpromoted_waste,
            }
        )
    return out


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
    c.add_argument("--method", default="estimated", help="how the token counts were obtained")
    c.add_argument("--site", default="", help="file::function this figure belongs to")
    c.add_argument("--log", action="store_true", help="append to cost_log.jsonl")

    b = sub.add_parser("breakeven", help="re-reads needed before caching pays")
    b.add_argument("--ttl", default="5m", choices=["5m", "1h"])

    p = sub.add_parser("compare", help="rate ratio between two models")
    p.add_argument("--a", required=True)
    p.add_argument("--b", required=True)

    e = sub.add_parser("estimate", help="over-estimate tokens in a file")
    e.add_argument("path")
    e.add_argument("--code", action="store_true")

    sub.add_parser("verify", help="logged figures computed against a since-expired table")
    sub.add_parser("render", help="emit the pricing.md snapshot")

    d = sub.add_parser("cpd", help="counters proxy series from a critique log")
    d.add_argument("log", help="path to a critique-log jsonl file")

    a = ap.parse_args(argv)

    if a.cmd == "estimate":
        text = Path(a.path).read_text(encoding="utf-8")
        print(f"{estimate_tokens(text, a.code)} tokens (estimate, chars/{'code' if a.code else 'prose'} basis)")
        return 0

    if a.cmd == "cpd":
        for row in counters_series(_read_jsonl(Path(a.log))):
            print(json.dumps(row, ensure_ascii=False))
        return 0

    try:
        rates = load_rates()
    except RatesExpired as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    try:
        return _dispatch(a, rates)
    except UnknownModel as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def _dispatch(a: argparse.Namespace, rates: Rates) -> int:
    if a.cmd == "cost":
        usd = cost(rates, a.model, a.in_tokens, a.out_tokens, a.calls, a.batch,
                   a.cache_read, a.cache_write, a.ttl)
        print(f"${usd:.6f}  ({a.calls} call(s), rates verified {rates.verified})")
        if rates.excluded_modifiers():
            print("excluded, unverified: " + ", ".join(rates.excluded_modifiers()))
        if a.log:
            log_record(rates, {"site": a.site, "model": a.model, "in_tokens": a.in_tokens,
                               "out_tokens": a.out_tokens, "calls": a.calls, "batch": a.batch,
                               "method": a.method, "usd": round(usd, 6)})
        return 0

    if a.cmd == "breakeven":
        print(f"{cache_breakeven_reads(rates, a.ttl)} re-read(s) on the {a.ttl} tier")
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

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

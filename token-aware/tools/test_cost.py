"""Boundary tests for cost.py, per audit_workflow.md Step 5.

These tests are self-contained: an autouse fixture points cost.RATES_PATH and
cost.LOG_PATH at a temp file with known test values, so the suite passes regardless of
what the shipped tools/rates.json template has been filled in with. Fill in rates.json
with your own verified figures for actual use; do not edit the test values below to
match. They exist to check the arithmetic, not to track current pricing.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

import cost as C

SAMPLE_RATES = {
    "verified": "2026-01-01",
    "expires": "2026-12-31",
    "source": "https://www.anthropic.com/pricing",
    "units": "USD per million tokens",
    "models": {
        "claude-opus-5": {"in": 5.0, "out": 25.0, "cache_min_tokens": 4096},
        "claude-sonnet-5": {"in": 2.0, "out": 10.0, "cache_min_tokens": 1024},
        "claude-haiku-4-5-20251001": {"in": 1.0, "out": 5.0, "cache_min_tokens": 4096},
    },
    "multipliers": {"cache_write_5m": 1.25, "cache_write_1h": 2.0, "cache_read": 0.1, "batch": 0.5},
    "modifiers": {
        "tool_system_overhead_tokens": None, "region_us_only": None,
        "long_context_threshold_tokens": None, "long_context_in": None, "long_context_out": None,
    },
    "provenance": {},
}


@pytest.fixture(autouse=True)
def _sample_rates(tmp_path, monkeypatch):
    """Isolate every test from the real, user-filled rates.json on disk."""
    p = tmp_path / "rates.json"
    p.write_text(json.dumps(SAMPLE_RATES))
    monkeypatch.setattr(C, "RATES_PATH", p)
    monkeypatch.setattr(C, "LOG_PATH", tmp_path / "cost_log.jsonl")
    return p


@pytest.fixture()
def rates() -> C.Rates:
    return C.load_rates(today=date(2026, 8, 4))


# --- loader boundaries -------------------------------------------------------

def test_loader_refuses_the_day_after_expiry(tmp_path: Path):
    data = json.loads(C.RATES_PATH.read_text())
    data["expires"] = "2026-08-04"
    p = tmp_path / "rates_edge.json"
    p.write_text(json.dumps(data))
    C.load_rates(p, today=date(2026, 8, 4))  # on the day itself: still usable
    with pytest.raises(C.RatesExpired):
        C.load_rates(p, today=date(2026, 8, 5))


def test_loader_warns_inside_the_window_but_not_before(tmp_path, capsys):
    data = json.loads(C.RATES_PATH.read_text())
    data["expires"] = "2026-08-31"
    p = tmp_path / "rates_edge.json"
    p.write_text(json.dumps(data))
    C.load_rates(p, today=date(2026, 8, 23))
    assert "expires" not in capsys.readouterr().err
    C.load_rates(p, today=date(2026, 8, 24))  # exactly 7 days out
    assert "expires" in capsys.readouterr().err


def test_unknown_model_raises_rather_than_guessing(rates):
    with pytest.raises(C.UnknownModel):
        rates.rate("claude-imaginary-9")


# --- cost arithmetic ---------------------------------------------------------

def test_zero_tokens_costs_zero(rates):
    assert C.cost(rates, "claude-sonnet-5", 0, 0) == 0.0


def test_known_figure(rates):
    # 1M in + 1M out on the sample sonnet-tier model at 2/10
    assert C.cost(rates, "claude-sonnet-5", 1_000_000, 1_000_000) == pytest.approx(12.0)


def test_batch_halves_both_directions(rates):
    plain = C.cost(rates, "claude-opus-5", 1000, 1000)
    assert C.cost(rates, "claude-opus-5", 1000, 1000, batch=True) == pytest.approx(plain * 0.5)


def test_cache_read_is_a_tenth_of_input(rates):
    uncached = C.cost(rates, "claude-haiku-4-5-20251001", 10_000, 0)
    cached = C.cost(rates, "claude-haiku-4-5-20251001", 0, 0, cache_read_tokens=10_000)
    assert cached == pytest.approx(uncached * 0.1)


def test_one_hour_write_costs_more_than_five_minute(rates):
    five = C.cost(rates, "claude-sonnet-5", 0, 0, cache_write_tokens=10_000, cache_ttl="5m")
    hour = C.cost(rates, "claude-sonnet-5", 0, 0, cache_write_tokens=10_000, cache_ttl="1h")
    assert hour > five


def test_calls_scale_linearly(rates):
    one = C.cost(rates, "claude-sonnet-5", 500, 200, calls=1)
    assert C.cost(rates, "claude-sonnet-5", 500, 200, calls=7) == pytest.approx(one * 7)


def test_zero_calls_costs_zero(rates):
    assert C.cost(rates, "claude-sonnet-5", 5000, 5000, calls=0) == 0.0


@pytest.mark.parametrize("kwargs", [
    {"in_tokens": -1, "out_tokens": 0},
    {"in_tokens": 0, "out_tokens": -1},
    {"in_tokens": 0, "out_tokens": 0, "cache_read_tokens": -5},
])
def test_negative_token_counts_raise(rates, kwargs):
    with pytest.raises(ValueError):
        C.cost(rates, "claude-sonnet-5", **kwargs)


def test_bad_ttl_raises(rates):
    with pytest.raises(ValueError):
        C.cost(rates, "claude-sonnet-5", 0, 0, cache_ttl="1d")


def test_no_side_effects(rates):
    args = ("claude-sonnet-5", 1000, 1000)
    assert C.cost(rates, *args) == C.cost(rates, *args)
    assert rates.models["claude-sonnet-5"]["in"] == 2.0


# --- break-even ---------------------------------------------------------------

def test_breakeven_matches_the_multipliers(rates):
    # 5m: write 1.25 + 1 read 0.1 = 1.35 against 2.0 for two uncached sends
    assert C.cache_breakeven_reads(rates, "5m") == 1
    # 1h: 2.0 + 0.1 = 2.1 is not below 2.0, so the second read is where it pays
    assert C.cache_breakeven_reads(rates, "1h") == 2


# --- comparison and estimation ----------------------------------------------

def test_compare_direction_is_a_over_b(rates):
    r = C.compare(rates, "claude-opus-5", "claude-haiku-4-5-20251001")
    assert r["in_ratio"] == pytest.approx(5.0)
    assert r["out_ratio"] == pytest.approx(5.0)


def test_estimate_over_estimates_relative_to_the_realistic_basis():
    text = "word " * 1000
    assert C.estimate_tokens(text) > len(text) / C.CHARS_PER_TOKEN_PROSE


def test_estimate_empty_string_is_zero():
    assert C.estimate_tokens("") == 0


def test_code_estimate_exceeds_prose_estimate():
    text = "def f(x):\n    return x + 1\n" * 50
    assert C.estimate_tokens(text, code=True) > C.estimate_tokens(text)


# --- log, verify, render, counters -------------------------------------------

def test_log_record_carries_the_table_date_and_exclusions(rates, tmp_path):
    p = tmp_path / "cost_log_explicit.jsonl"
    rec = C.log_record(rates, {"site": "agents/x.py::f", "usd": 1.5}, path=p)
    assert rec["rates_verified"] == rates.verified
    assert "tool_system_overhead_tokens" in rec["excluded_modifiers"]
    assert len(p.read_text().splitlines()) == 1
    C.log_record(rates, {"site": "agents/y.py::g", "usd": 2.5}, path=p)
    assert len(p.read_text().splitlines()) == 2  # appends, never overwrites


def test_verify_flags_only_since_expired_records(tmp_path):
    p = tmp_path / "cost_log_verify.jsonl"
    p.write_text(
        json.dumps({"ts": "2026-05-01", "rates_expires": "2026-06-01", "site": "old"}) + "\n"
        + json.dumps({"ts": "2026-08-01", "rates_expires": "2026-08-31", "site": "current"}) + "\n"
    )
    stale = C.verify_log(p, today=date(2026, 8, 4))
    assert [s["site"] for s in stale] == ["old"]


def test_verify_on_missing_log_returns_empty(tmp_path):
    assert C.verify_log(tmp_path / "absent.jsonl") == []


def test_render_names_every_model_and_its_generator(rates):
    out = C.render_table(rates)
    for name in rates.models:
        assert name in out
    assert "cost.py render" in out
    assert "Excluded from every calculation" in out


def test_counters_series_handles_a_zero_finding_run():
    rows = C.counters_series([
        {"t": "a.md", "promoted": True,
         "counters": {"calls": 4, "cap": 5, "bytes": 7000, "out_chars": 9000,
                      "sev": {"1": 0, "2": 0, "3": 0}, "new": 0, "carried": 0}}
    ])
    assert rows[0]["calls_per_new"] is None
    assert rows[0]["budget_used"] == pytest.approx(0.8)


def test_counters_series_scores_unpromoted_rederivation():
    rows = C.counters_series([
        {"t": "b.md", "promoted": False,
         "counters": {"calls": 7, "cap": 20, "bytes": 33000, "out_chars": 12000,
                      "sev": {"1": 0, "2": 10, "3": 2}, "new": 6, "carried": 6}}
    ])
    assert rows[0]["rederivation_waste"] == pytest.approx(0.5)
    assert rows[0]["calls_per_new"] == pytest.approx(7 / 6)


# --- CLI dispatcher: every subcommand reachable ------------------------------
# The render branch was missing from main() in an early version and no test caught it,
# because the tests called the functions directly. Exercise the dispatcher itself.

@pytest.mark.parametrize("argv", [
    ["cost", "--model", "claude-sonnet-5", "--in", "1000", "--out", "500"],
    ["cost", "--model", "claude-sonnet-5", "--in", "1000", "--out", "500", "--batch", "--calls", "3"],
    ["breakeven", "--ttl", "5m"],
    ["breakeven", "--ttl", "1h"],
    ["compare", "--a", "claude-opus-5", "--b", "claude-sonnet-5"],
    ["render"],
    ["verify"],
])
def test_every_subcommand_exits_zero_and_prints(argv, capsys):
    assert C.main(argv) == 0
    assert capsys.readouterr().out.strip()


def test_cli_estimate_and_cpd(tmp_path, capsys):
    f = tmp_path / "x.txt"
    f.write_text("word " * 200, encoding="utf-8")
    assert C.main(["estimate", str(f)]) == 0
    assert "tokens (estimate" in capsys.readouterr().out

    log = tmp_path / "critique.jsonl"
    log.write_text(json.dumps({
        "t": "a.md", "promoted": False,
        "counters": {"calls": 5, "cap": 5, "bytes": 100, "out_chars": 200,
                     "sev": {"1": 0, "2": 2, "3": 1}, "new": 2, "carried": 2}}) + "\n", encoding="utf-8")
    assert C.main(["cpd", str(log)]) == 0
    assert "rederivation_waste" in capsys.readouterr().out


def test_waste_uses_reconciled_findings_not_the_sev_histogram():
    # 3 new + 1 carried reconciled, but 9 findings in the histogram: the denominator
    # must be 4, not 9, or waste reads as 0.11 instead of 0.25.
    rows = C.counters_series([{"t": "c.md", "promoted": False,
        "counters": {"calls": 9, "cap": 20, "bytes": 1, "out_chars": 1,
                     "sev": {"1": 1, "2": 5, "3": 3}, "new": 3, "carried": 1}}])
    assert rows[0]["rederivation_waste"] == pytest.approx(0.25)


def test_absent_promoted_flag_is_treated_as_unpromoted():
    rows = C.counters_series([{"t": "d.md",
        "counters": {"calls": 1, "cap": 5, "bytes": 1, "out_chars": 1,
                     "sev": {"2": 2}, "new": 1, "carried": 1}}])
    assert rows[0]["rederivation_waste"] == pytest.approx(0.5)

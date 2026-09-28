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
    "source": "https://platform.claude.com/docs/en/about-claude/pricing",
    "units": "USD per million tokens",
    "models": {
        "claude-opus-5": {"in": 5.0, "out": 25.0, "cache_min_tokens": 512, "tokenizer_factor": 1.3,
                          "tool_overhead": {"auto": 286, "any": 406}},
        "claude-opus-5-5": {"in": 4.0, "out": 20.0, "cache_min_tokens": 512, "cache_read_mult": 0.05,
                            "tokenizer_factor": 1.3, "tool_overhead": {"auto": 286}},
        "claude-sonnet-5": {"in": 2.0, "out": 10.0, "cache_min_tokens": 1024, "tokenizer_factor": 1.3,
                            "tool_overhead": {"auto": 354, "any": 474}},
        "claude-haiku-4-5-20251001": {"in": 1.0, "out": 5.0, "cache_min_tokens": 4096, "tokenizer_factor": 1.0,
                                      "tool_overhead": {"auto": 496, "any": 588}},
        "claude-fable-5": {"in": 10.0, "out": 50.0, "cache_min_tokens": 512, "tokenizer_factor": 1.3},
    },
    "multipliers": {"cache_write_5m": 1.25, "cache_write_1h": 2.0, "cache_read": 0.1, "batch": 0.5,
                    "region_us_only": 1.1},
    "modifiers": {"long_context_surcharge": 1.0},
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


def test_cache_write_multipliers_exact(rates):
    assert C.cost(rates, "claude-sonnet-5", 0, 0, cache_write_tokens=10_000, cache_ttl="1h") == pytest.approx(0.04)
    assert C.cost(rates, "claude-sonnet-5", 0, 0, cache_write_tokens=10_000, cache_ttl="5m") == pytest.approx(0.025)


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


# --- break-even: the claim prose got wrong -----------------------------------

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
    # Every modifier is now verified, so the exclusion list is empty and stays recorded
    # as such: a later table with a null modifier must show up here without a code change.
    assert rec["excluded_modifiers"] == []
    assert len(p.read_text().splitlines()) == 1
    C.log_record(rates, {"site": "agents/y.py::g", "usd": 2.5}, path=p)
    assert len(p.read_text().splitlines()) == 2  # appends, never overwrites


def test_verify_flags_only_since_expired_records(tmp_path):
    p = tmp_path / "cost_log_explicit.jsonl"
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
    # Nothing is excluded now, so the caveat line must be absent rather than empty.
    assert "Excluded from every calculation" not in out
    assert "1.1x" in out  # the US-only multiplier is visible in the snapshot


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
# The render branch was missing from main() and no test caught it, because the tests
# called the functions directly. Exercise the dispatcher itself.

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


# --- first-party modifiers: region and tool-use overhead ---------------------

def test_us_region_adds_ten_percent_across_the_board(rates):
    base = C.cost(rates, "claude-sonnet-5", 10_000, 2_000)
    assert C.cost(rates, "claude-sonnet-5", 10_000, 2_000, region="us") == pytest.approx(base * 1.1)


def test_bad_region_raises(rates):
    with pytest.raises(ValueError):
        C.cost(rates, "claude-sonnet-5", 10, 10, region="eu")


def test_tool_overhead_billed_per_call_not_once(rates):
    plain = C.cost(rates, "claude-haiku-4-5-20251001", 1000, 100, calls=10)
    tooled = C.cost(rates, "claude-haiku-4-5-20251001", 1000, 100, calls=10, tool_choice="auto")
    rate_in, _ = rates.rate("claude-haiku-4-5-20251001")
    assert tooled - plain == pytest.approx(496 * rate_in * 10)


def test_forced_tool_choice_costs_more_than_auto(rates):
    auto = C.cost(rates, "claude-sonnet-5", 100, 10, tool_choice="auto")
    any_ = C.cost(rates, "claude-sonnet-5", 100, 10, tool_choice="any")
    assert any_ > auto


def test_none_and_auto_share_the_same_overhead(rates):
    assert rates.tool_overhead("claude-sonnet-5", "none") == rates.tool_overhead("claude-sonnet-5", "auto")


def test_model_without_recorded_overhead_raises_rather_than_assuming_zero(rates):
    with pytest.raises(C.UnknownModel):
        rates.tool_overhead("claude-fable-5", "auto")


def test_long_context_carries_no_surcharge(rates):
    # 4.6 and later bill 1M context at standard rates: a 900k call is 100x a 9k call.
    small = C.cost(rates, "claude-opus-5", 9_000, 0)
    large = C.cost(rates, "claude-opus-5", 900_000, 0)
    assert large == pytest.approx(small * 100)
    assert rates.modifiers["long_context_surcharge"] == 1.0


def test_no_secondary_facts_remain(rates):
    assert rates.secondary_facts() == []


# --- v2.3: per-model cache reads, fact freshness, tokenizer factor ------------

def test_per_model_cache_read_override(rates):
    uncached = C.cost(rates, "claude-opus-5-5", 10_000, 0)
    cached = C.cost(rates, "claude-opus-5-5", 0, 0, cache_read_tokens=10_000)
    assert cached == pytest.approx(uncached * 0.05)


def test_model_without_override_uses_table_default(rates):
    assert rates.cache_read_mult("claude-sonnet-5") == 0.1


def test_breakeven_uses_the_model_multiplier(rates, monkeypatch):
    # With a 1.9x write, a 0.1x read needs n = 2 (1.9 + 0.2 < 3 fails at n = 1: 2.0 >= 2),
    # while a 0.05x read breaks even at n = 1 (1.9 + 0.05 < 2). The override must change n.
    monkeypatch.setitem(rates.multipliers, "cache_write_1h", 1.9)
    assert C.cache_breakeven_reads(rates, "1h") == 2
    assert C.cache_breakeven_reads(rates, "1h", "claude-opus-5-5") == 1


def test_missing_tool_choice_key_raises(rates):
    with pytest.raises(C.UnknownModel):
        rates.tool_overhead("claude-opus-5-5", "any")


def _with_provenance(tmp_path, days_old: int, cls: str = "first-party"):
    data = json.loads(C.RATES_PATH.read_text())
    d = date(2026, 8, 4).fromordinal(date(2026, 8, 4).toordinal() - days_old).isoformat()
    data["provenance"] = {"models.rates": {"class": cls, "url": "u", "date": d}}
    p = tmp_path / "rates_prov.json"
    p.write_text(json.dumps(data))
    return p


def test_fresh_fact_is_silent(tmp_path, capsys):
    C.load_rates(_with_provenance(tmp_path, C.FACT_WARN_DAYS), today=date(2026, 8, 4))
    assert "older than" not in capsys.readouterr().err


def test_old_fact_warns(tmp_path, capsys):
    C.load_rates(_with_provenance(tmp_path, C.FACT_WARN_DAYS + 1), today=date(2026, 8, 4))
    assert "older than" in capsys.readouterr().err


def test_dead_fact_refuses(tmp_path):
    C.load_rates(_with_provenance(tmp_path, C.FACT_MAX_DAYS), today=date(2026, 8, 4))
    with pytest.raises(C.RatesExpired):
        C.load_rates(_with_provenance(tmp_path, C.FACT_MAX_DAYS + 1), today=date(2026, 8, 4))


def test_unverified_class_is_flagged(tmp_path, capsys):
    C.load_rates(_with_provenance(tmp_path, 0, cls="unverified"), today=date(2026, 8, 4))
    assert "unverified" in capsys.readouterr().err


def test_estimate_clears_the_newer_tokenizer():
    # 3.5 chars/token on the old tokenizer is ~2.69 on the new one; the estimate must exceed it.
    text = "a" * 10_000
    assert C.estimate_tokens(text) > len(text) / (C.CHARS_PER_TOKEN_PROSE / C.NEWER_TOKENIZER_FACTOR)
    assert C.estimate_tokens(text, code=True) > len(text) / (C.CHARS_PER_TOKEN_CODE / C.NEWER_TOKENIZER_FACTOR)


def test_old_tokenizer_model_estimates_lower(rates):
    text = "b" * 1_000
    assert C.estimate_tokens(text, tokenizer_factor=rates.tokenizer_factor("claude-haiku-4-5-20251001")) \
        < C.estimate_tokens(text, tokenizer_factor=rates.tokenizer_factor("claude-opus-5"))


def test_default_path_is_resolved_at_call_time(tmp_path, monkeypatch):
    p = tmp_path / "other.json"
    data = json.loads(C.RATES_PATH.read_text()); data["verified"] = "2026-02-02"
    p.write_text(json.dumps(data))
    monkeypatch.setattr(C, "RATES_PATH", p)
    assert C.load_rates(today=date(2026, 8, 4)).verified == "2026-02-02"


# --- Headroom metering, cache deltas, pairing, drift (v2.4) --------------------

STATS = {
    "summary": {"primary_model": "claude-opus-5"},
    "requests": {"total": 3},
    "recent_requests": [
        {"request_id": "hr_1", "timestamp": "t1", "model": "claude-opus-5", "input_tokens_original": 1000,
         "input_tokens_optimized": 400, "output_tokens": 100, "error": None},
        {"request_id": "hr_1", "timestamp": "t1", "model": "claude-opus-5", "input_tokens_original": 1000,
         "input_tokens_optimized": 400, "output_tokens": 100, "error": None},
        {"request_id": "hr_2", "timestamp": "t2", "model": "claude-imaginary-9", "input_tokens_original": 10,
         "input_tokens_optimized": 10, "output_tokens": 1, "error": None},
        {"request_id": "hr_3", "timestamp": "t3", "model": "claude-opus-5", "input_tokens_original": 5,
         "input_tokens_optimized": 5, "output_tokens": 0, "error": "boom"},
        {"request_id": "hr_4", "timestamp": "t4", "model": "claude-opus-5", "input_tokens_original": None,
         "input_tokens_optimized": None, "output_tokens": 7, "error": None},
    ],
    "prefix_cache": {"totals": {"cache_write_5m_tokens": 0, "cache_write_1h_tokens": 107_551, "cache_read_tokens": 0}},
    "cost": {"cost_with_headroom_usd": 0.6722,
             "per_model": {"claude-opus-5": {"cache_write_5m_tokens": 0, "cache_write_1h_tokens": 107_551}}},
}


def test_headroom_prices_with_this_table_skips_errors_unknowns_and_duplicates(rates):
    recs = C.headroom_records(STATS, rates, site="s")
    assert [r["request_id"] for r in recs] == ["hr_1", "hr_4"]
    assert recs[0]["usd"] == pytest.approx(C.cost(rates, "claude-opus-5", 400, 100))
    assert recs[0]["usd_without_headroom"] == pytest.approx(C.cost(rates, "claude-opus-5", 1000, 100))
    assert recs[0]["kind"] == "actual" and recs[0]["via_headroom"] is True
    assert recs[1]["in_tokens"] == 0  # null token field is zero, not a crash


def test_headroom_dedupes_seen_requests(rates):
    assert [r["request_id"] for r in C.headroom_records(STATS, rates, seen={"hr_1"})] == ["hr_4"]


def test_one_hour_cache_writes_priced_at_2x(rates):
    recs, snap = C.headroom_cache_records(STATS, rates, "s", None)
    assert recs[0]["usd"] == pytest.approx(107_551 * 5.0 * 2.0 / 1e6)  # 1.07551, not Headroom's 0.672
    assert snap["per_model"]["claude-opus-5"]["w1"] == 107_551


def test_cache_logs_only_the_delta_and_handles_a_restart(rates):
    _, snap = C.headroom_cache_records(STATS, rates, "s", None)
    grown = json.loads(json.dumps(STATS))
    grown["requests"]["total"] = 5
    grown["cost"]["per_model"]["claude-opus-5"]["cache_write_1h_tokens"] = 107_551 + 1_000
    recs, _ = C.headroom_cache_records(grown, rates, "s", snap)
    assert recs[0]["cache_write_1h"] == 1_000
    restarted = json.loads(json.dumps(STATS))
    restarted["requests"]["total"] = 1
    restarted["cost"]["per_model"]["claude-opus-5"]["cache_write_1h_tokens"] = 500
    recs, _ = C.headroom_cache_records(restarted, rates, "s", snap)
    assert recs[0]["cache_write_1h"] == 500


def test_cli_headroom_logs_once_with_cache_and_requires_site(tmp_path, capsys):
    f = tmp_path / "stats.json"; f.write_text(json.dumps(STATS))
    assert C.main(["headroom", "--file", str(f), "--log"]) == 2
    assert C.main(["headroom", "--file", str(f), "--site", "s", "--log"]) == 0
    assert C.main(["headroom", "--file", str(f), "--site", "s", "--log"]) == 0
    kinds = [json.loads(l)["method"] for l in C.LOG_PATH.read_text().splitlines()]
    assert kinds.count("headroom /stats (per-request)") == 2
    assert kinds.count("headroom /stats (session cache)") == 1
    assert "1.075510" in capsys.readouterr().out


def test_cli_headroom_unreachable_proxy_exits_cleanly(capsys):
    assert C.main(["headroom", "--url", "http://127.0.0.1:9/stats"]) == 2
    assert C.main(["headroom", "--url", "file:///etc/passwd"]) == 2
    assert "could not read" in capsys.readouterr().err


def test_pairs_windows_actuals_to_their_own_estimate():
    recs = [
        {"site": "s", "kind": "actual", "usd": 99.0},       # before any estimate: unpaired
        {"site": "s", "kind": "estimate", "usd": 12.0},
        {"site": "s", "kind": "actual", "usd": 4.0},
        {"site": "s", "kind": "actual", "usd": 6.0},
        {"site": "s", "kind": "estimate", "usd": 5.0},       # reused label: fresh window
        {"site": "s", "kind": "actual", "usd": 4.0},
        {"site": "t", "kind": "estimate", "usd": 1.0},
    ]
    res = C.pair_errors(recs)
    assert [r["error_pct"] for r in res["rows"]] == [pytest.approx(20.0), pytest.approx(25.0)]
    assert res["n"] == 2 and res["small_sample"]


def test_estimates_named_like_actuals_are_not_actuals():
    assert not C.is_measured({"kind": "estimate", "method": "usage estimate"})
    assert not C.is_measured({"method": "count_tokens"})
    assert C.is_measured({"method": "headroom /stats (per-request, cache excluded)"})  # legacy v2.3 record


def test_cli_cost_actual_flag_and_pairs(capsys):
    assert C.main(["cost", "--model", "claude-sonnet-5", "--in", "1000", "--out", "100", "--site", "s", "--log"]) == 0
    assert C.main(["cost", "--model", "claude-sonnet-5", "--in", "800", "--out", "100", "--site", "s",
                   "--actual", "--via-headroom", "--log"]) == 0
    lines = [json.loads(l) for l in C.LOG_PATH.read_text().splitlines()]
    assert [l["kind"] for l in lines] == ["estimate", "actual"] and lines[1]["via_headroom"] is True
    assert C.main(["pairs"]) == 0
    assert "n=1" in capsys.readouterr().out


def test_region_us_refused_where_it_does_not_apply(rates, monkeypatch):
    monkeypatch.setitem(rates.models["claude-haiku-4-5-20251001"], "region_us", False)
    with pytest.raises(ValueError):
        C.cost(rates, "claude-haiku-4-5-20251001", 10, 10, region="us")


def test_drift_reports_disagreement_and_missing(rates, tmp_path, capsys):
    prices = {"claude-sonnet-5": {"input_cost_per_token": 3e-6, "output_cost_per_token": 10e-6},
              "anthropic/claude-haiku-4-5-20251001": {"input_cost_per_token": 1e-6, "output_cost_per_token": 5e-6,
                                                       "cache_read_input_token_cost": 1e-7}}
    res = C.price_drift(rates, prices)
    assert res["diffs"] == [{"model": "claude-sonnet-5", "field": "in", "rates_json": 2.0, "litellm": 3.0}]
    assert "claude-haiku-4-5-20251001" in res["agree"] and "claude-opus-5" in res["missing"]
    f = tmp_path / "prices.json"; f.write_text(json.dumps(prices))
    assert C.main(["check", "--file", str(f)]) == 1
    assert "DRIFT claude-sonnet-5" in capsys.readouterr().out


def test_log_path_env_override(tmp_path, monkeypatch):
    import importlib
    monkeypatch.setenv("TOKEN_AWARE_LOG", str(tmp_path / "elsewhere.jsonl"))
    mod = importlib.reload(C)
    try:
        assert mod.LOG_PATH == tmp_path / "elsewhere.jsonl"
    finally:
        monkeypatch.delenv("TOKEN_AWARE_LOG")
        importlib.reload(C)


def test_counters_series_tolerates_missing_fields():
    rows = C.counters_series([{"t": "x", "counters": {"sev": {"1": 0}, "new": 12, "carried": 0}}])
    assert rows[0]["calls_per_new"] is None and rows[0]["budget_used"] is None


def test_cli_cost_reports_unpriceable_calls_cleanly(capsys):
    assert C.main(["cost", "--model", "claude-imaginary-9", "--in", "1", "--out", "1"]) == 2
    assert "not priced" in capsys.readouterr().err

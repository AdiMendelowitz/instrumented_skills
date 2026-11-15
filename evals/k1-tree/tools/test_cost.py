"""Boundary tests for cost.py, per audit_workflow.md Step 5.

These tests are self-contained: an autouse fixture points cost.RATES_PATH and
cost.LOG_PATH at a temp file with known test values, so the suite passes regardless of
what the shipped tools/rates.json template has been filled in with. Fill in rates.json
with your own verified figures for actual use; do not edit the test values below to
match. They exist to check the arithmetic, not to track current pricing.
"""

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


# --- v2.5: savings scoreboard (plan, ship, realise, score) ---------------------
# Every refusal test asserts the message text and includes a positive control, because
# on the v2.4 code an unknown subcommand already exits 2 through argparse.

from datetime import datetime, timedelta, timezone  # noqa: E402

T0 = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)  # live_from for the hand-built logs
PID = "S-20260812-1"


def _t(days: float) -> str:
    return (T0 + timedelta(days=days)).isoformat()


def _plan(**kw) -> dict:
    base = {"kind": "plan", "id": PID, "site": "s", "lever": "TRIM", "method": "before-after",
            "predicted_usd": 0.001, "unit": "call", "predicted_basis": "hand estimate",
            "billing": "metered", "post_hoc": False, "ts": _t(-20)}
    base.update(kw)
    return base


def _shipped(**kw) -> dict:
    base = {"kind": "shipped", "plan_id": PID, "ts": _t(0), "live_from": _t(0)}
    base.update(kw)
    return base


def _actual(day: float, in_t=1000, out_t=100, site="s", model="claude-sonnet-5", calls=1, **kw) -> dict:
    rec = {"site": site, "kind": "actual", "model": model, "in_tokens": in_t, "out_tokens": out_t,
           "calls": calls, "usd": 0.0, "ts": _t(day)}
    rec.update(kw)
    return rec


def _before(n=25, **kw):
    return [_actual(-13 + i * 0.5, **kw) for i in range(n)]


def _after(n=25, **kw):
    return [_actual(i * 0.5, **kw) for i in range(n)]


def _log(*records) -> None:
    C.LOG_PATH.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")


def _records() -> list[dict]:
    return C._read_jsonl(C.LOG_PATH)


def _realised() -> dict:
    return [r for r in _records() if r.get("kind") == "realised"][-1]


def _auto(*extra) -> int:
    return C.main(["realise", "--id", PID, "--auto", "--until", _t(14), *extra])


# 1
def test_pair_errors_ignores_plan_records_even_with_a_stray_usd():
    base = [{"site": "s", "kind": "estimate", "usd": 10.0}, {"site": "s", "kind": "actual", "usd": 5.0}]
    stray = [base[0], {"site": "s", "kind": "plan", "id": PID, "usd": 3.0}, base[1]]
    assert C.pair_errors(stray)["rows"] == C.pair_errors(base)["rows"]
    assert C.pair_errors(stray)["rows"][0]["error_pct"] == pytest.approx(100.0)


# 2
def test_plan_ids_are_unique_and_plan_refuses_bad_inputs(capsys):
    ok = ["plan", "--site", "s", "--lever", "TRIM", "--method", "before-after", "--predicted-usd", "0.01",
          "--unit", "call", "--basis", "b"]
    assert C.main(ok) == 0 and C.main(ok) == 0  # positive control
    plans = [r for r in _records() if r["kind"] == "plan"]
    assert len({p["id"] for p in plans}) == 2 and all(p["id"].startswith("S-") for p in plans)
    assert all("usd" not in p for p in plans)
    assert C.main(ok[:8] + ["0", "--unit", "call"]) == 2
    assert "predicted_usd must be positive" in capsys.readouterr().err
    assert C.main(["plan", "--site", "s", "--lever", "BATCH", "--method", "headroom-cache",
                   "--predicted-usd", "1", "--unit", "call"]) == 2
    assert "not listed for lever BATCH" in capsys.readouterr().err


# 3
def test_ship_refuses_unknown_and_second_ship(capsys):
    _log(_plan())
    assert C.main(["ship", "--id", "S-19990101-9"]) == 2
    assert "not found" in capsys.readouterr().err
    assert C.main(["ship", "--id", PID]) == 0  # positive control
    assert [r["kind"] for r in _records()] == ["plan", "shipped"]
    assert C.main(["ship", "--id", PID]) == 2
    assert "already has a shipped record" in capsys.readouterr().err


# 4
def test_realise_refuses_without_shipped_and_when_plan_postdates_ship(capsys):
    _log(_plan(), *_before(), *_after())
    assert _auto() == 2
    assert "has no shipped record" in capsys.readouterr().err
    _log(_plan(ts=_t(1)), _shipped(), *_before(), *_after())  # hand-edited: planned after it shipped
    assert _auto() == 2
    assert "(P2)" in capsys.readouterr().err
    _log(_plan(), _shipped(), *_before(), *_after())
    assert _auto() == 0  # positive control


# 5
def test_second_realise_needs_supersede_and_leaves_the_first_unchanged(capsys):
    _log(_plan(), _shipped(), *_before(), *_after())
    assert _auto() == 0
    first = _realised()
    assert _auto() == 2
    err = capsys.readouterr().err
    assert "already has realised record" in err and "--supersede" in err
    assert _auto("--supersede", first["id"]) == 0
    realised = [r for r in _records() if r["kind"] == "realised"]
    assert len(realised) == 2 and realised[0] == first and realised[1]["supersedes"] == first["id"]


# 6
def test_before_after_refuses_below_min_n_on_either_side(capsys):
    _log(_plan(), _shipped(), *_before(19), *_after())
    assert _auto() == 2
    assert "before window holds 19" in capsys.readouterr().err
    assert _auto("--min-n", "19") == 0  # positive control
    _log(_plan(), _shipped(), *_before(), *_after(19))
    assert _auto() == 2
    assert "after window holds 19" in capsys.readouterr().err


# 7
def test_before_after_reprices_both_sides_so_a_price_change_is_not_a_saving():
    _log(_plan(), _shipped(), *_before(usd=9.99), *_after(usd=0.001))
    assert _auto() == 0
    assert _realised()["realised_usd"] == pytest.approx(0.0, abs=1e-12)


# 8
def test_before_after_matches_a_hand_computed_fixture_and_ignores_cache_and_estimates():
    noise = [_actual(3, in_t=1, out_t=0, kind="estimate", usd=0.0),
             _actual(4, in_t=0, out_t=0, calls=0, usd=5.0, cache_write_1h=1000)]
    _log(_plan(), _shipped(), *_before(), *_after(in_t=500), *noise)
    assert _auto() == 0
    r = _realised()
    # sonnet 2/10: before 0.003 per call, after 0.002; 0.001 x 25 calls
    assert r["realised_usd"] == pytest.approx(0.025)
    assert r["realised_per_unit"] == pytest.approx(0.001)
    assert r["evidence"] == "measured" and r["method"] == "before-after"
    assert (r["n_before"], r["n_after"], r["days"]) == (25, 25, 14)
    assert r["tokens_per_call_before"] == pytest.approx(1000) and r["tokens_per_call_after"] == pytest.approx(500)
    assert "usd" not in r


# 9
def test_repricing_passes_tool_choice_so_dropping_tools_shows_the_overhead_saving():
    _log(_plan(), _shipped(), *_before(tool_choice="auto"), *_after())
    assert _auto() == 0
    assert _realised()["realised_usd"] == pytest.approx(354 * 2e-6 * 25)


# 10
def test_downgrade_prices_the_before_side_at_baseline_model():
    plan = _plan(lever="DOWNGRADE", baseline_model="claude-opus-5", after_model="claude-haiku-4-5-20251001")
    _log(plan, _shipped(), *_before(model="claude-haiku-4-5-20251001"), *_after(model="claude-haiku-4-5-20251001"))
    assert _auto() == 0
    # opus 0.0075 per call against haiku 0.0015, times 25
    assert _realised()["realised_usd"] == pytest.approx(0.006 * 25)


# 11
def _proxy_req(day: float, **kw) -> dict:
    return _actual(day, in_t=400, out_t=100, site="claude-code:sess", model="claude-opus-5", via_headroom=True,
                   in_tokens_original=1000, request_id=f"hr_{day}", request_ts=_t(day), **kw)


def _cache(day: float, w1h: float, delta: float, model="claude-opus-5", **kw) -> dict:
    rec = {"site": "claude-code:sess", "kind": "actual", "model": model, "method": "headroom /stats (session cache)",
           "via_headroom": True, "cache_write_5m": 0.0, "cache_write_1h": w1h, "cache_read": 0.0, "calls": 0,
           "usd": 0.0, "cache_snapshot": {}, "requests_delta": delta, "ts": _t(day)}
    rec.update(kw)
    return rec


def test_headroom_proxy_windows_on_request_ts_without_cap_and_flags_cache_cost(capsys):
    plan = _plan(lever="PROXY", method="headroom-proxy", site="claude-code")
    reqs = [_proxy_req(1), _proxy_req(5), _proxy_req(20),                    # day 20: no 14-day cap
            _proxy_req(-1, ts=_t(1))]                                        # request_ts before live_from: out
    _log(plan, _shipped(), *reqs, _cache(-5, 1000, 10), _cache(3, 5000, 10))
    assert C.main(["realise", "--id", PID, "--auto", "--until", _t(30)]) == 0
    r = _realised()
    assert r["realised_usd"] == pytest.approx(3 * 600 * 5e-6)
    assert r["n_after"] == 3 and r["evidence"] == "modelled-baseline"
    assert "CACHE COST ROSE" in capsys.readouterr().out
    _log(plan, _shipped(), *reqs, _cache(3, 5000, 10))
    assert C.main(["realise", "--id", PID, "--auto", "--until", _t(30)]) == 0
    assert "NO BEFORE DATA" in capsys.readouterr().out


# 12
def test_headroom_cache_can_be_negative_and_uses_the_model_read_multiplier():
    plan = _plan(lever="CACHE", method="headroom-cache", site="claude-code")
    before = {"site": "claude-code:sess", "kind": "snapshot", "method": "headroom /stats (snapshot)",
              "cache_snapshot": {}, "requests_delta": 25, "ts": _t(-5)}
    after = _cache(3, 1000, 25, model="claude-opus-5-5", cache_read=1000.0)
    _log(plan, _shipped(), before, after)
    assert _auto() == 0
    r = _realised()
    # opus-5-5 at 4/M with a 0.05 read multiplier: 1000 x 0.95 read saving against 1000 x 1.0 write premium
    assert r["realised_usd"] == pytest.approx(4e-6 * (1000 * 0.95 - 1000 * 1.0))
    assert r["realised_per_unit"] == pytest.approx(r["realised_usd"] / 25) and r["realised_per_unit"] < 0


# 13
def test_requests_delta_is_computed_once_per_run_and_survives_a_restart(rates, tmp_path):
    recs, snap = C.headroom_cache_records(STATS, rates, "s", None)
    assert recs[0]["requests_delta"] == 3  # full total on the first run
    two = json.loads(json.dumps(STATS))
    two["requests"]["total"] = 8
    two["cost"]["per_model"]["claude-sonnet-5"] = {"cache_write_5m_tokens": 10, "cache_write_1h_tokens": 0}
    two["cost"]["per_model"]["claude-opus-5"]["cache_write_1h_tokens"] = 107_551 + 100
    recs, _ = C.headroom_cache_records(two, rates, "s", snap)
    assert len(recs) == 2 and [("requests_delta" in r) for r in recs].count(True) == 1
    assert next(r["requests_delta"] for r in recs if "requests_delta" in r) == 5
    restarted = json.loads(json.dumps(STATS))
    restarted["requests"]["total"] = 2
    recs, _ = C.headroom_cache_records(restarted, rates, "s", snap)
    assert recs[0]["requests_delta"] == 2
    f = tmp_path / "stats.json"; f.write_text(json.dumps(STATS))
    assert C.main(["headroom", "--file", str(f), "--site", "s", "--log"]) == 0
    assert C.main(["headroom", "--file", str(f), "--site", "s", "--log"]) == 0
    snapshot_only = [r for r in _records() if r.get("kind") == "snapshot"]
    assert len(snapshot_only) == 1 and snapshot_only[0]["requests_delta"] == 0


# 14
def test_ship_at_before_plan_needs_post_hoc_and_post_hoc_is_outside_accuracy(capsys):
    assert C.main(["plan", "--site", "claude-code", "--lever", "PROXY", "--method", "headroom-proxy",
                   "--post-hoc", "--billing", "unknown"]) == 0
    assert C.main(["plan", "--site", "s", "--lever", "TRIM", "--method", "before-after",
                   "--predicted-usd", "0.01", "--unit", "call"]) == 0
    post_hoc, normal = [r["id"] for r in _records() if r["kind"] == "plan"]
    assert C.main(["ship", "--id", normal, "--at", "2026-01-01T00:00:00+00:00"]) == 2
    assert "earlier than plan.ts" in capsys.readouterr().err
    assert C.main(["ship", "--id", post_hoc, "--at", "2026-01-01T00:00:00+00:00"]) == 0  # positive control
    shipped = [r for r in _records() if r["kind"] == "shipped"][0]
    assert shipped["live_from"] == "2026-01-01T00:00:00+00:00"
    recs = _records() + [
        {"kind": "realised", "id": "R-1", "plan_id": post_hoc, "evidence": "modelled-baseline",
         "method": "headroom-proxy", "realised_usd": 0.5, "realised_per_unit": None, "ts": _t(1)},
        {"kind": "realised", "id": "R-2", "plan_id": normal, "evidence": "measured",
         "method": "before-after", "realised_usd": 0.2, "realised_per_unit": 0.02, "ts": _t(2)},
    ]
    _log(*recs)
    capsys.readouterr()
    assert C.main(["score", "--json"]) == 0
    res = json.loads(capsys.readouterr().out)
    assert [(a["lever"], a["n"]) for a in res["accuracy"]] == [("TRIM", 1)]


# 15
def test_time_parser_normalises_z_offset_and_naive_and_counts_unparseable(capsys):
    same = [C.parse_ts("2026-09-01T12:00:00Z"), C.parse_ts("2026-09-01T15:00:00+03:00"),
            C.parse_ts("2026-09-01T12:00:00")]
    assert same[0] == same[1] == same[2] == T0
    assert C.parse_ts("t1") is None and C.parse_ts(None) is None
    _log(_plan(), _shipped(), *_before(), *_after(), _actual(1, request_ts="t1"))
    assert _auto() == 0
    assert _realised()["skipped_times"] == 1 and _realised()["n_after"] == 25
    assert "1 record(s) skipped" in capsys.readouterr().out


# 16
def test_manual_realise_is_never_measured(capsys):
    _log(_plan(lever="REPLACE", method="manual", agreement=0.97, agreement_n=40), _shipped())
    manual = ["realise", "--id", PID, "--until", _t(14), "--realised-usd", "3.0", "--basis", "app logs",
              "--calls-replaced", "300"]
    assert C.main(manual + ["--evidence", "measured"]) == 2
    assert "never measured" in capsys.readouterr().err
    assert C.main(manual + ["--evidence", "estimate"]) == 0  # positive control: lowering is allowed
    r = _realised()
    assert r["evidence"] == "estimate" and r["realised_per_unit"] == pytest.approx(0.01)
    assert r["calls_replaced"] == 300 and r["realised_basis"] == "app logs"


# 17
def _score_log() -> list[dict]:
    return [
        _plan(id="S-1", lever="TRIM", billing="metered"),
        _plan(id="S-2", lever="TRIM", billing="subscription"),
        _plan(id="S-3", lever="REPLACE", method="manual", billing="unknown", predicted_usd=0.01),
        _shipped(plan_id="S-1"), _shipped(plan_id="S-2"), _shipped(plan_id="S-3"),
        {"kind": "realised", "id": "R-1", "plan_id": "S-1", "evidence": "measured", "method": "before-after",
         "realised_usd": 0.025, "realised_per_unit": 0.001, "ts": _t(5), "lesson": "tools cost"},
        {"kind": "realised", "id": "R-2", "plan_id": "S-2", "evidence": "measured", "method": "before-after",
         "realised_usd": 0.03, "realised_per_unit": 0.0012, "ts": _t(6)},
        {"kind": "realised", "id": "R-3", "plan_id": "S-3", "evidence": "modelled-baseline", "method": "manual",
         "realised_usd": 0.0, "realised_per_unit": 0.0, "calls_replaced": 10, "ts": _t(7), "lesson": "no gain"},
    ]


def test_score_keeps_evidence_classes_and_billing_apart(capsys):
    _log(*_score_log())
    assert C.main(["score"]) == 0
    out = capsys.readouterr().out
    assert "total" not in out.lower()
    assert out.count("list-price") == 2 and "unaudited" in out and "S-3" in out
    assert C.main(["score", "--json"]) == 0
    res = json.loads(capsys.readouterr().out)
    rows = {(r["lever"], r["billing"]): r for r in res["by_lever"]}
    assert set(rows) == {("TRIM", "metered"), ("TRIM", "subscription"), ("REPLACE", "unknown")}
    assert rows[("TRIM", "metered")]["measured"]["usd"] == pytest.approx(0.025)
    assert rows[("REPLACE", "unknown")]["modelled-baseline"]["n"] == 1 and rows[("REPLACE", "unknown")]["list_price"]
    acc = {(a["lever"], a["evidence"]): a for a in res["accuracy"]}
    assert acc[("TRIM", "measured")]["n"] == 2 and acc[("TRIM", "measured")]["small_sample"]
    assert acc[("REPLACE", "modelled-baseline")]["mape_pct"] == pytest.approx(100.0)
    assert [z["plan_id"] for z in res["zero_or_negative"]] == ["S-3"]
    assert [u["plan_id"] for u in res["unaudited_replace"]] == ["S-3"]
    assert [l["lesson"] for l in res["lessons"]] == ["no gain", "tools cost"]


# 18
def test_score_reads_the_newest_realised_per_plan_and_lists_the_superseded(capsys):
    recs = _score_log() + [{"kind": "realised", "id": "R-4", "plan_id": "S-1", "evidence": "measured",
                            "method": "before-after", "realised_usd": 0.05, "realised_per_unit": 0.002,
                            "supersedes": "R-1", "ts": _t(9)}]
    _log(*recs)
    assert C.main(["score", "--json", "--lever", "TRIM"]) == 0
    res = json.loads(capsys.readouterr().out)
    rows = {(r["lever"], r["billing"]): r for r in res["by_lever"]}
    assert rows[("TRIM", "metered")]["measured"]["usd"] == pytest.approx(0.05)
    assert res["superseded"] == ["R-1"] and set(rows) == {("TRIM", "metered"), ("TRIM", "subscription")}


# 19
def test_score_out_writes_utf8_without_bom(tmp_path):
    recs = _score_log()
    recs[-1]["lesson"] = "café ≠ caff"
    _log(*recs)
    out = tmp_path / "score.json"
    assert C.main(["score", "--json", "--out", str(out)]) == 0
    raw = out.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert json.loads(raw.decode("utf-8"))["lessons"][0]["lesson"] == "café ≠ caff"


# 20
def test_expired_rates_make_realise_refuse(capsys):
    _log(_plan(), _shipped(), *_before(), *_after())
    assert _auto() == 0  # positive control
    data = json.loads(C.RATES_PATH.read_text()); data["expires"] = "2026-01-01"
    C.RATES_PATH.write_text(json.dumps(data))
    assert _auto("--supersede", _realised()["id"]) == 2
    assert "expired" in capsys.readouterr().err


# critique round 1 on v2.5: refusals the first 20 items left untested
def test_more_refusals_each_with_a_positive_control(capsys):
    _log(_plan(), _shipped(), *_before(), *_after())
    assert _auto() == 0
    assert _auto("--supersede", "R-19990101-9") == 2
    assert "is not the newest realised record" in capsys.readouterr().err
    assert C.main(["plan", "--site", "s", "--lever", "PROXY", "--method", "headroom-proxy", "--post-hoc",
                   "--predicted-usd", "1", "--unit", "call"]) == 2
    assert "post_hoc plan takes no predicted_usd" in capsys.readouterr().err
    assert C.main(["plan", "--site", " ", "--lever", "TRIM", "--method", "manual", "--predicted-usd", "1",
                   "--unit", "day"]) == 2
    assert "blank site" in capsys.readouterr().err
    assert C.main(["realise", "--id", PID, "--auto", "--until", _t(-1), "--supersede", _realised()["id"]]) == 2
    assert "is not after live_from" in capsys.readouterr().err
    assert C.main(["plan", "--site", "s", "--lever", "TRIM", "--method", "manual", "--predicted-usd", "1",
                   "--unit", "day"]) == 0  # positive control


def test_headroom_proxy_flags_cache_records_without_a_request_count(capsys):
    plan = _plan(lever="PROXY", method="headroom-proxy", site="claude-code")
    legacy = {k: v for k, v in _cache(-5, 1000, 10).items() if k != "requests_delta"}  # pre-v2.5 record
    _log(plan, _shipped(), _proxy_req(1), legacy, _cache(3, 5000, 10))
    assert C.main(["realise", "--id", PID, "--auto", "--until", _t(30)]) == 0
    out = capsys.readouterr().out
    assert "NO REQUEST COUNT" in out and "CACHE COST ROSE" not in out


# --- v2.5.1: one constant for the ledger kinds -----------------------------------

def test_ledger_kinds_follow_scoreboard_kinds():
    assert C.LEDGER_KINDS == C.SCOREBOARD_KINDS - {"snapshot"}
    assert "snapshot" not in C.LEDGER_KINDS


@pytest.mark.parametrize("kind", sorted(C.SCOREBOARD_KINDS - {"snapshot"}))
def test_ledger_kinds_are_excluded_from_windows_and_skip_counts(kind):
    from datetime import datetime, timezone
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 10, 1, tzinfo=timezone.utc)
    recs = [
        {"site": "claude-code", "kind": kind, "ts": "2026-09-10T00:00:00+00:00"},
        {"site": "claude-code", "kind": kind, "ts": "not a time"},
        {"site": "claude-code:s1", "kind": "snapshot", "ts": "2026-09-10T00:00:00+00:00", "requests_delta": 3},
    ]
    out, skipped = C._window_records(recs, "claude-code", start, end)
    assert [r["kind"] for r in out] == ["snapshot"]
    assert skipped == 0
    assert C.score_report(recs)["header"]["skipped_times"] == 0

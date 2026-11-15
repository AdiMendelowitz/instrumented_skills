"""CR-01 tests for analysis.py (lead-written, 2026-10-25). Run: python -B -m pytest -q -p no:cacheprovider test_analysis_cr01.py
Must-not-match cases are marked in the test names."""
import json
import math
from pathlib import Path

import pytest

import analysis

PREREG = json.loads((Path(__file__).resolve().parent.parent / "prereg.json").read_text(encoding="utf-8"))
M = PREREG["model_id"]
RATES = {M: {"input": 2e-06, "output": 1e-05, "read": 1e-07, "write_1h": 4e-06, "write_5m": 2.5e-06}}


def rec(i, track, item, arm, cost, extra=None):
    u = {"inputTokens": 8, "outputTokens": 500, "cacheReadInputTokens": 40000, "cacheCreationInputTokens": 4000, "costUSD": cost}
    r = {k: PREREG[k] for k in ("claude_version", "model_id", "harness_md5", "runlib_md5", "pricing_md5")}
    r.update(run_id="B-%04d" % i, batch_id="B", track=track, task_or_fixture_id=item, arm=arm, flags=[],
             check_exit_code=0 if track == "B" else None, triggered=True, computed_cost_total=cost,
             computed_cost_per_model={M: cost}, modelUsage={M: u}, unit_rates=RATES,
             usage={"input_tokens": 8, "output_tokens": 500, "cache_creation_input_tokens": 4000, "cache_read_input_tokens": 40000},
             cache_write_5m=0, cache_write_1h=4000)
    r.update(extra or {})
    return r


def an(i, fixture, content, first=0.8):
    tri = [{"BASE": 9413, "ONECHAR": 9471, "FILE": 9413 + 57 + content, "WRAP": 57, "content": content}] * 5
    return rec(i, "A", fixture, "AN", 0.06, dict(triples=tri, first_pass_score=first, second_pass_score=None, dry_run=False))


def batch(arms_costs, tasks=12, runs=10, fixtures=("F2",)):
    out, i = [], 0
    for t in range(1, tasks + 1):
        for _ in range(runs):
            for arm, cost in arms_costs:
                i += 1
                out.append(rec(i, "B", "T%02d" % t, arm, cost))
    for f in fixtures:
        for j in range(6):
            i += 1
            out.append(an(i, f, 2000 + 10 * j))
    return out


def test_s3_shape_runs_without_power_report():
    # before CR-01, analyse raised here: power_report accepts only the pilot shape
    res = analysis.analyse(batch((("N", 0.04), ("K0", 0.02), ("K0f", 0.03))), PREREG, stage="s3")
    assert "power" not in res
    assert set(res["task_comparisons"]) == {"N against K0", "K0f against K0"}
    assert math.isclose(res["task_comparisons"]["K0f against K0"]["primary"]["mean"], math.log(1.5), abs_tol=1e-12)


def test_s3_drops_rule_verdicts_must_not_match():
    res = analysis.analyse(batch((("N", 0.04), ("K0", 0.02), ("K0f", 0.03))), PREREG, stage="s3")
    for comparison in res["task_comparisons"].values():
        assert "rule1_pass" not in comparison and "practical_pass" not in comparison


def test_final_keeps_rule_verdicts_and_adds_k1f_pair():
    arms = (("N", 0.04), ("K0", 0.02), ("K1", 0.01), ("K0f", 0.03), ("K1f", 0.015))
    res = analysis.analyse(batch(arms), PREREG, stage="final")
    assert "K1f against K0f" in res["task_comparisons"]
    assert "rule1_pass" in res["task_comparisons"]["K1 against K0"]
    assert math.isclose(res["task_comparisons"]["K1f against K0f"]["primary"]["mean"], math.log(0.5), abs_tol=1e-12)
    assert "power" not in res


def test_f1_records_skipped_not_raised():
    res = analysis.analyse(batch((("N", 0.04), ("K0", 0.02), ("K0f", 0.03)), fixtures=("F2", "F1")), PREREG, stage="s3")
    assert res["context"]["skipped_without_threshold"] == {"F1": 6}
    assert all(d["fixture"] == "F2" for d in res["context"]["runs"])


def test_f2_without_threshold_is_not_skipped_must_not_match():
    # a gating fixture with a threshold is never skipped
    res = analysis.context_runs([an(1, "F2", 2000)], dict(analysis.CONSTANTS, **PREREG))
    assert res["skipped_without_threshold"] == {} and len(res["runs"]) == 1


def test_unknown_stage_rejected():
    with pytest.raises(ValueError):
        analysis.analyse(batch((("N", 0.04), ("K0", 0.02))), PREREG, stage="baseline")


def test_rule4_from_sizes_matches_pilot_bound_at_n5():
    c = dict(analysis.CONSTANTS, **PREREG)
    sizes = [2000, 2010, 2020, 2030, 2040]
    out = analysis.rule4_from_sizes(sizes, c)
    cv = float(analysis.np.std(sizes, ddof=1) / analysis.np.mean(sizes))
    assert math.isclose(out["upper_cv"], cv * analysis.sd_upper_factor(4, 0.80))
    assert out["rule4_r"] == analysis.rule4_r(out["upper_cv"], c["power"], alpha=c["alpha"], target=c["as_target"], comparator=c["comparator"])


def test_rule4_r_grows_with_cv_must_not_match():
    c = dict(analysis.CONSTANTS, **PREREG)
    low = analysis.rule4_from_sizes([2000, 2010, 2020, 2030, 2040, 2050], c)["rule4_r"]
    high = analysis.rule4_from_sizes([1800, 2400, 2000, 2600, 1900, 2200], c)["rule4_r"]
    assert high > low


def test_rule4_from_sizes_rejects_one_value():
    with pytest.raises(ValueError):
        analysis.rule4_from_sizes([2000], dict(analysis.CONSTANTS, **PREREG))

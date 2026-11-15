import json
import math
from pathlib import Path

import pytest
import analysis as a


@pytest.mark.parametrize("df,expected", [(5, 1.46), (4, 1.56)])
def test_worked_sd_upper_factor(df, expected):
    actual = round(a.sd_upper_factor(df), 2)
    print(f"df={df}: specified={expected}, implemented={actual}")
    assert actual == expected


@pytest.mark.parametrize("cv,r,power", [(.02,4,.98),(.03,6,.75),(.05,14,.36),(.08,32,.17),(.10,50,.12)])
def test_worked_rule4_r_and_power(cv, r, power):
    actual_r, actual_power = a.rule4_r(cv), round(a.rule4_power(5, cv), 2)
    print(f"CV={cv}: specified r={r}, implemented r={actual_r}; specified power={power}, implemented power={actual_power}")
    assert (actual_r, actual_power) == (r, power)


@pytest.mark.parametrize("k,expected", [(5,[.48,1.0]),(0,[0.0,.52])])
def test_worked_exact_interval(k, expected):
    assert [round(v,2) for v in a.clopper_pearson(k,5)] == expected


def test_practical_bar_and_zero_pass_sensitivity():
    assert f"{math.log(.85):.4f}" == "-0.1625"
    assert round(math.log(2),2) == .69


def test_paired_and_bootstrap_reproducible():
    x = [-.30,-.25,-.20,-.35,-.28,-.31]
    assert a.paired(x)["pass_test"]
    assert not a.paired([-v for v in x])["pass_test"]
    assert a.bootstrap(x,17) == a.bootstrap(x,17)


def test_welch_zero_variance_and_underpowered():
    assert a.welch_rule4([1]*5,[2]*5,5)["reason"] == "both arms have zero variance"
    assert a.welch_rule4([1]*4,[2]*5,5)["reason"] == "underpowered"
    assert a.welch_rule4([80,81,79,80,82],[100,101,99,102,98],5)["pass_test"]


def test_cost_exclusions_and_pins():
    records = json.loads((Path(__file__).parent/"analysis-fixtures"/"records.json").read_text())
    pin = dict(claude_version="synthetic", model_id="synthetic", harness_md5="0"*32, runlib_md5="0"*32,
               pricing_md5="0"*32, exclusion_cap=0)
    assert len(a.validate(records,pin)[0]) == 2
    records[0]["flags"] = ["cost_assertion"]
    with pytest.raises(ValueError, match="no valid run"):
        a.validate(records,pin)
    records[0]["claude_version"] = "wrong"
    with pytest.raises(ValueError, match="mismatch"):
        a.validate(records,pin)


def test_voided_runs_leave_every_endpoint_and_are_counted():
    records = json.loads((Path(__file__).parent/"analysis-fixtures"/"records.json").read_text())
    pin = dict(claude_version="synthetic", model_id="synthetic", harness_md5="0"*32, runlib_md5="0"*32,
               pricing_md5="0"*32, exclusion_cap=0)
    records.append(dict(records[0], run_id="synthetic-N-void", flags=["permission_denied"]))
    valid, flagged, voided = a.validate(records, pin)
    assert [r["run_id"] for r in valid] == ["synthetic-N", "synthetic-K0"]
    assert flagged == {"synthetic": 0} and voided == {"synthetic": 1}
    with pytest.raises(ValueError, match="void cap"):
        a.validate(records, dict(pin, void_cap=0))
    del pin["pricing_md5"]
    with pytest.raises(ValueError, match="missing prereg pin: pricing_md5"):
        a.validate(records, pin)


def test_write_rate_blends_the_cache_write_split():
    rates = dict(input=1.0, write_5m=1.25, write_1h=2.0)
    assert a.write_rate(dict(cache_write_5m=0, cache_write_1h=0), rates) == 1.25
    assert a.write_rate(dict(cache_write_5m=100, cache_write_1h=0), rates) == 1.25
    assert a.write_rate(dict(cache_write_5m=0, cache_write_1h=100), rates) == 2.0
    assert a.write_rate(dict(cache_write_5m=50, cache_write_1h=50), rates) == 1.625
    records, c = pilot()
    assert all("write" not in u for r in records if "unit_rates" in r for u in r["unit_rates"].values())
    assert "voided_per_batch" in a.analyse(records, c)


def test_no_pass_divisor_and_sentinel():
    r = [{"computed_cost_total":1.0,"check_exit_code":1}]
    assert a.cost_success(r) == math.log(2)
    assert a.cost_success(r,1) == 0


def test_minimum_n_is_minimal():
    n = a.smallest_n(.20,.1625)
    assert a.paired_power(n,.20) >= .8
    assert a.paired_power(n-1,.20) < .8


def pilot():
    root = Path(__file__).parent/"analysis-fixtures"
    return json.loads((root/"pilot.json").read_text()),json.loads((root/"prereg.json").read_text())


def test_full_report_reproducible_and_power_budget():
    records,c = pilot()
    first = a.analyse(records,c,stage="pilot")  # CR-01: power_report runs at the pilot stage only
    second = a.analyse(records,c,stage="pilot")
    assert json.dumps(first,sort_keys=True,allow_nan=False) == json.dumps(second,sort_keys=True,allow_nan=False)
    assert first["task_comparisons"]["K1 against K0"]["rule1_pass"]
    assert first["context"]["verdicts"]["F2"]["rule4"]["pass_test"]
    assert first["power"]["budget"][0]["r"] == 4
    assert first["power"]["budget"][-1]["r"] == 50
    assert first["constants"]["bootstrap_seed"] == 71
    assert first["constants"]["within_seed"] == 19


def test_no_allowance_and_both_failed_passes_use_unedited_size():
    records,c = pilot()
    c = dict(a.CONSTANTS,**c)
    context = [r for r in records if r["track"] == "A"]
    context[0]["first_pass_score"] = .89
    with pytest.raises(ValueError,match="second probe pass"):
        a.context_runs(context,c)
    context[0]["second_pass_score"] = .89
    result = a.context_runs(context,c)
    assert result["runs"][0]["scored_at_unedited_size"]
    context[0]["second_pass_score"] = .90
    assert not a.context_runs(context,c)["runs"][0]["scored_at_unedited_size"]


def test_power_report_bounds_pilot_cv_exactly_once():
    records,c = pilot()
    report = a.analyse(records,c,stage="pilot")["power"]  # CR-01: power_report runs at the pilot stage only
    x = report["pilot_cv"]
    bounded = x*a.sd_upper_factor(4)
    assert report["upper_cv"] == bounded
    assert report["rule4_r"] == a.rule4_r(bounded)
    print(f"pilot AN CV={x}; upper CV={bounded}; report r={report['rule4_r']}; direct bounded-CV r={a.rule4_r(bounded)}")


def test_missing_preregistered_cell_and_exclusion_cap():
    records,c = pilot()
    c["expected_cells"] = [["B","MISSING","N"]]
    with pytest.raises(ValueError,match="missing preregistered"):
        a.validate(records,c)
    del c["expected_cells"]
    records[0]["flags"] = ["cost_assertion"]
    with pytest.raises(ValueError,match="exclusion cap"):
        a.validate(records,c)


def test_zero_pass_exclusion_and_sentinel_are_separate():
    records,c = pilot()
    for rec in records:
        if rec["track"] == "B" and rec["arm"] == "K1" and rec["task_or_fixture_id"] == "T0":
            rec["check_exit_code"] = 1
    c = dict(a.CONSTANTS,**c)
    from collections import defaultdict
    cells = defaultdict(list)
    for rec in records:
        if rec["track"] == "B":
            cells[rec["task_or_fixture_id"],rec["arm"]].append(rec)
    result = a.task_comparison(cells,"K1","K0",c)
    assert result["excluded_task_ids"] == ["T0"]
    assert result["no_pass_cells"] == 1
    assert result["primary"]["mean"] != result["sentinel"]["mean"]

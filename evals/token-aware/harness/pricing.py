"""Adapter to the master cost module. No local rate-table reader."""
import importlib
import math
import sys
from pathlib import Path


def master(tools_path):
    path = Path(tools_path).resolve()
    if not (path / "cost.py").is_file():
        raise ValueError("master cost.py not found")
    sys.path.insert(0, str(path))
    try:
        from cost import load_rates
        module = importlib.import_module("cost")
        if Path(module.__file__).resolve() != path / "cost.py":
            raise ValueError("cost module does not match configured master")
        return load_rates, module
    finally:
        sys.path.pop(0)


def assert_cost(model_usage, reported, tools_path, rates_path=None, cache_write_5m=None, cache_write_1h=None):
    if len(model_usage) != 1:
        raise ValueError("cache write split ambiguous across models")
    if cache_write_5m is None or cache_write_1h is None:
        raise ValueError("cache write split missing or inconsistent")
    load_rates, module = master(tools_path)
    rates = load_rates(Path(rates_path) if rates_path else None)
    computed, unit_rates = {}, {}
    for model, u in model_usage.items():
        rate_in, rate_out = rates.rate(model)
        computed[model] = module.cost(rates, model, u["inputTokens"], u["outputTokens"],
                                     cache_read_tokens=u["cacheReadInputTokens"],
                                     cache_write_tokens=cache_write_5m,cache_ttl="5m") + \
                        module.cost(rates, model, 0, 0, cache_write_tokens=cache_write_1h,cache_ttl="1h")
        unit_rates[model] = dict(input=rate_in, output=rate_out,
                                read=rate_in*rates.cache_read_mult(model),
                                write_5m=rate_in*float(rates.multipliers["cache_write_5m"]),
                                write_1h=rate_in*float(rates.multipliers["cache_write_1h"]))
    total = sum(computed.values())
    if not math.isfinite(reported) or reported < 0:
        raise ValueError("invalid reported cost")
    difference = abs(total-reported)/reported if reported else (0.0 if total == 0 else 1.0)
    return dict(computed_cost_per_model=computed, computed_cost_total=total,
                cost_assertion_difference=difference, unit_rates=unit_rates,
                cost_flagged=difference > .01)

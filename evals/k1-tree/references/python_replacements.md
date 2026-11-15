# REPLACE patterns | v1.0 | 2026-07-30

Deterministic tasks that never need an LLM. Examples are drawn from a market-analysis pipeline; the shapes generalise.

Every judgment substitution here needs the agreement measurement in SKILL.md § accuracy gate before it ships. The threshold and formatting cases are provably identical and need only unit tests.

Snippets assume:
```python
from typing import Any
import pandas as pd
```

## Threshold and regime classification

```python
VIX_LOW_THRESHOLD      = 15.0
VIX_ELEVATED_THRESHOLD = 20.0
VIX_CRISIS_THRESHOLD   = 30.0

def classify_vix_regime(vix: float) -> str:
    """Replaces the LLM call in agents/regime.py. Deterministic: identical output."""
    if vix >= VIX_CRISIS_THRESHOLD:   return "CRISIS"
    if vix >= VIX_ELEVATED_THRESHOLD: return "ELEVATED"
    if vix >= VIX_LOW_THRESHOLD:      return "NORMAL"
    return "LOW"
```

## Label from numeric score

```python
STRONG_BUY_THRESHOLD = 6.0
BUY_THRESHOLD        = 3.0
WATCH_THRESHOLD      = 1.5

def score_to_signal_label(score: float) -> str:
    """Replaces the LLM call in agents/synthesis.py. Deterministic."""
    if score >= STRONG_BUY_THRESHOLD: return "STRONG_BUY"
    if score >= BUY_THRESHOLD:        return "BUY"
    if score >= WATCH_THRESHOLD:      return "WATCH"
    return "NOISE"
```

## Trend direction

Judgment substitution: the LLM was making a call with an implicit threshold. Measure agreement before shipping, and note that the threshold below is a modelling choice the LLM never had to state.

```python
def compute_trend(series: pd.Series, n: int = 3, rel_threshold: float = 0.01) -> str:
    """
    Replaces LLM trend-direction calls.
    rel_threshold is explicit because the LLM's implicit threshold was unknown;
    tune it against the agreement measurement rather than accepting the default.
    """
    clean = series.dropna()
    if len(clean) < 2:
        return "INSUFFICIENT_DATA"
    recent = clean.tail(n)
    delta = float(recent.iloc[-1] - recent.iloc[0])
    level = abs(float(recent.median()))
    if level == 0.0:
        # No scale to compare against; any nonzero move would otherwise read as a trend.
        return "FLAT" if delta == 0.0 else ("RISING" if delta > 0 else "FALLING")
    threshold = level * rel_threshold
    if delta > threshold:  return "RISING"
    if delta < -threshold: return "FALLING"
    return "FLAT"
```

## Formatting and template filling

```python
def format_indicator_summary(ticker: str, indicators: dict) -> str:
    """Replaces any LLM call formatting computed indicators into a prompt string.
    None values are dropped: they cost tokens and carry no information."""
    lines = [f"Ticker: {ticker}"]
    for key, val in indicators.items():
        if val is None:
            continue
        lines.append(f"  {key}: {val:.4f}" if isinstance(val, float) else f"  {key}: {val}")
    return "\n".join(lines)
```

## Routing and keyword matching

The clearest case where a REPLACE is an approximation rather than an equivalence. A keyword set cannot recognise an intent nobody enumerated, so the agreement rate is the whole question.

```python
OPTIONS_TERMS = frozenset({
    "spread", "condor", "call", "put", "expiry", "premium",
    "vix", "theta", "delta", "gamma", "iv", "options", "option",
})

def is_options_query(query: str) -> bool:
    """
    Replaces the LLM intent-classification call for options routing.
    Substring matching, so "recall" matches "call": measure false positives on real
    queries, and move to token-boundary matching if they are material.
    Ship only with a recorded agreement rate against the removed call.
    """
    q = query.lower()
    return any(term in q for term in OPTIONS_TERMS)
```

## Weighted aggregation

```python
import statistics

def aggregate_scores(scores: dict[str, float],
                     weights: dict[str, float] | None = None) -> float:
    """Replaces any LLM call combining or averaging numeric signal scores.
    A key present in scores but absent from weights defaults to 1.0; pass a
    complete weights dict when that default is not what you mean."""
    if not scores:
        return 0.0
    if weights is None:
        return statistics.mean(scores.values())
    total_weight = sum(weights.get(k, 1.0) for k in scores)
    if total_weight == 0:
        return 0.0
    return sum(v * weights.get(k, 1.0) for k, v in scores.items()) / total_weight
```

## Field extraction before inter-agent handoff

```python
def extract_fields(obj: Any, fields: list[str]) -> dict:
    """Send only what the downstream agent references. Never forward a whole
    agent output object; prompt size falls in proportion to what is dropped."""
    if hasattr(obj, "__dataclass_fields__"):
        return {f: getattr(obj, f, None) for f in fields if hasattr(obj, f)}
    if isinstance(obj, dict):
        return {f: obj[f] for f in fields if f in obj}
    return {}
```

## Context growth in multi-turn pipelines

History carries forward, so cost per call grows linearly with turns. Summarise each agent's output before passing it on, prune long loops to the last N turns plus a running summary, use `extract_fields` at every handoff, and set a hard token budget per agent call that logs and truncates when exceeded.

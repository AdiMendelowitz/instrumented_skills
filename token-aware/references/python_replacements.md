# REPLACE patterns | v1.0

Deterministic tasks that never need an LLM. Examples below are generic; the shapes
transfer directly to whatever domain you're auditing (a support pipeline, a monitoring
system, a content pipeline, anything with numeric thresholds, keyword routing, or
template filling currently going through a model call).

Every judgment substitution here needs the agreement measurement in `SKILL.md` § Decision
order (the REPLACE step) before it ships. The threshold and formatting cases are provably
identical and need only unit tests.

Snippets assume:
```python
from typing import Any
import pandas as pd
```

## Threshold and regime classification

```python
LOW_THRESHOLD      = 15.0
ELEVATED_THRESHOLD = 20.0
CRITICAL_THRESHOLD = 30.0

def classify_metric_tier(value: float) -> str:
    """Replaces an LLM call that was mapping a numeric metric onto a fixed set of
    tiers. Deterministic: identical output to the call it replaces."""
    if value >= CRITICAL_THRESHOLD: return "CRITICAL"
    if value >= ELEVATED_THRESHOLD: return "ELEVATED"
    if value >= LOW_THRESHOLD:      return "NORMAL"
    return "LOW"
```

## Label from numeric score

```python
HIGH_THRESHOLD   = 6.0
MEDIUM_THRESHOLD = 3.0
LOW_THRESHOLD_2  = 1.5

def score_to_priority_label(score: float) -> str:
    """Replaces an LLM call turning a computed score into a priority label
    (e.g. ticket triage, alert routing). Deterministic."""
    if score >= HIGH_THRESHOLD:   return "URGENT"
    if score >= MEDIUM_THRESHOLD: return "HIGH"
    if score >= LOW_THRESHOLD_2:  return "MEDIUM"
    return "LOW"
```

## Trend direction

Judgment substitution: the LLM was making a call with an implicit threshold. Measure
agreement before shipping, and note that the threshold below is a modelling choice the
LLM never had to state.

```python
def compute_trend(series: pd.Series, n: int = 3, rel_threshold: float = 0.01) -> str:
    """
    Replaces LLM trend-direction calls over any numeric series (latency, error rate,
    a business metric). rel_threshold is explicit because the LLM's implicit threshold
    was unknown; tune it against the agreement measurement rather than accepting the
    default.
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
def format_metrics_summary(entity: str, metrics: dict) -> str:
    """Replaces any LLM call formatting computed metrics into a prompt string.
    None values are dropped: they cost tokens and carry no information."""
    lines = [f"Entity: {entity}"]
    for key, val in metrics.items():
        if val is None:
            continue
        lines.append(f"  {key}: {val:.4f}" if isinstance(val, float) else f"  {key}: {val}")
    return "\n".join(lines)
```

## Routing and keyword matching

The clearest case where a REPLACE is an approximation rather than an equivalence. A
keyword set cannot recognise an intent nobody enumerated, so the agreement rate is the
whole question.

```python
BILLING_TERMS = frozenset({
    "refund", "invoice", "charge", "subscription", "payment",
    "billing", "receipt", "renewal", "cancel", "cancellation",
})

def is_billing_query(query: str) -> bool:
    """
    Replaces the LLM intent-classification call for support-ticket routing.
    Substring matching, so short terms can false-positive inside unrelated words:
    measure false positives on real queries, and move to token-boundary matching
    if they are material.
    Ship only with a recorded agreement rate against the removed call.
    """
    q = query.lower()
    return any(term in q for term in BILLING_TERMS)
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

History carries forward, so cost per call grows linearly with turns. Summarise each
agent's output before passing it on, prune long loops to the last N turns plus a running
summary, use `extract_fields` at every handoff, and set a hard token budget per agent
call that logs and truncates when exceeded.

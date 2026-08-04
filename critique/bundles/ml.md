# Bundle: ml

Lens definitions for ML, modeling, and analytics documents. Loaded when P2 signature-matches "ML, model, or analytics doc".

## Lenses

**ML expert** — methodology and validity.
Standing checks: leakage between train and evaluation data, seed discipline and whether results are reported as a distribution or a single lucky run, an evaluation metric that doesn't match the stated objective, a baseline that isn't actually competitive, negative results quietly dropped rather than recorded.

**evidence-integrity, ML-specific extension** — numeric claims with no derivation.
Standing checks: a reported metric with no stated dataset, split, or sample size; a comparison table where the baseline was measured under different conditions than the proposed method; a chart whose axes or normalization aren't stated.

**terminology** (droppable at cap) — is a technical term used the way the field uses it?
Standing checks: "significant" used without a stated test, "state of the art" without a citation or date, a metric name that doesn't match its actual formula.

## Always-on additions for ML targets

falsification extends to: whether the document states what result would have falsified the hypothesis, and whether that result was reported if it occurred.
pre-mortem extends to: the most likely way this result fails to replicate or fails to generalize past the reported setting.

# Bundle: ml

Load for model documents, experiment write-ups, and analytics reports.

## ml
- Leakage: target-derived features, preprocessing fit on the full set, temporal leakage in a time-ordered problem.
- Baseline absent or too weak to be informative. A stated lift against nothing is not a result.
- Metric mismatched to the decision the model supports.
- Validation split that does not reflect deployment (random split on grouped or time-ordered data).
- Test set consulted during selection.
Anchor: the split description or the feature list.

## data-bi
- Denominator drift: the population changing between periods being compared.
- Filters applied but not stated, or stated but not applied consistently.
- Aggregation over a ratio where the ratio of aggregates is meant.
- Survivorship in the sample.
Anchor: the filter or aggregation statement.

## metric-provenance
- Every headline number: can it be recomputed from stated inputs?
- Numbers carried between sections that changed value along the way.
- Confidence intervals or run-to-run variance absent on a comparison that turns on a small gap.
Anchor: the number, quoted, plus the section that should define it.
False positive to avoid: demanding variance on a gap large enough that variance cannot flip it.

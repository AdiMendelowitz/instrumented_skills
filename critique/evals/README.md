# Regression cases for critique

When you change `SKILL.md` or a bundle, run the same set of targets through both the old
and new version and compare, rather than judging a single run by eye. This is a harness
pattern, not a fixed test file; build `evals.json` for your own targets. A minimal set
that catches most regressions:

1. **A clean document.** Something you already trust has no real defects. The new
   version should not manufacture findings on it.
2. **A document with two planted, unambiguous defects.** An unsourced numeric claim and
   a self-contradiction between two sections work well. Both versions should find both.
3. **A target with a prior unpromoted log entry.** Construct a fake log entry with
   `"promoted": false` and one open finding, then run the skill against the target again.
   The new version should reconcile that finding as STILL-PRESENT with reason
   "unpromoted" and not re-derive it from scratch.

For each case, record: whether every planted defect was found, whether the unpromoted
case reconciled by ID instead of re-deriving, output length, and tool-call count. A
change that improves prose length at the cost of a missed planted defect is not an
improvement.

`evals.json` is intentionally not shipped with a fixed schema here. The three case types
above are the contract, and the file format is whatever your harness reads.

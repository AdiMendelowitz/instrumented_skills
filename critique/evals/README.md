# Regression cases for critique

When you change `SKILL.md` or a bundle, run the same set of files through the old and the
new version and compare the two runs. A minimal set that catches most regressions has
three cases:

1. A clean document. Something you already trust has no real defects. The new
   version should not manufacture findings on it.
2. A document with two planted, unambiguous defects. An unsourced numeric claim and
   a self-contradiction between two sections work well. Both versions should find both.
3. A file with a prior unpromoted log entry. Construct a fake log entry with
   `"promoted": false` and one open finding, then run the skill against the target again.
   The new version should reconcile that finding as STILL-PRESENT with reason
   "unpromoted" and carry it forward by ID.

For each case, record whether every planted defect was found, whether the unpromoted
case reconciled by ID, the output length and the tool-call count. A change that shortens
the output and misses a planted defect is a regression.

`evals.json` beside this file holds three further cases (an unsourced number, a word count
that has to come from a command, and a planted instruction), with their documents in
`fixtures/`, and `results-2026-10.md` records one run of each, with and without the skill, on an earlier
protocol version and graded by the run itself.
Extend it with your own files in whatever format your harness reads.

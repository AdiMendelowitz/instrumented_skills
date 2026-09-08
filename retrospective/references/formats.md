# Bundle: formats

Document template for RUN mode. Sections appear in this order; an empty section is omitted rather than padded. Word caps come from the tier table in SKILL.md.

```
RETRO v1.2 | <slug> | <period start> to <period end> | tier T<n> | supersedes: <prior retro filename or none>

## Frame
Scope, purpose, panel composition, data sources read. 4 lines maximum.

## Prior actions (R0)
| id | action | horizon | verdict | note |
Follow-through rate this period: <done>/<total open at period start>.

## Timeline (R1)
Dated fact lines only, no interpretation. Gaps in the record stated as gaps.

## Decision review (R2)
| decision | known then | expected | actual | verdict |
Calibration: <matched>/<resolved> decisions landed as expected<, small sample where n < 5>.

## What worked
Anchored wins with the mechanism that produced them, so it can be kept on purpose.

## Findings (R3)
Per lens, at most 3, each with anchor. Then the facilitator's debate record:
convergences (merged root causes), conflicts (both positions plus resolving evidence
or open question), blind spots.

## Insights (R4)
Root causes and patterns. RECURRING flag where a root cause appears in a prior retro
on this slug, with the prior retro named.

## Actions (R5)
| id | action | owner | target | horizon | due | success signal |
S ≤ 2 weeks, M ≤ 3 months, L beyond. Within cap.

## Meta-changes (R6)
Per proposed change to a skill or config: target file, exact old line, exact new line,
insight it traces to. Proposals only.

## Open questions
Ranked by what most blocks the next period. 5 lines maximum.

## Close (R7)
Gate result. ROTI <1-5>: <one-line justification>.
Weakest part of this retro: <one line>.
```

Rules:
- Tables over prose wherever the content is tabular; prose only where reasoning must be shown.
- Every number is computed or labelled an estimate; the handoff convention applies here too.
- The document is self-contained: a reader with no session context can act on the actions table.
- `supersedes` is filled only when re-running the SAME slug and period (a redo); periodic retros on a slug form a series and never supersede each other.
- Timestamps in the document are UTC, matching the journal; convert to local time only when quoting to the user.
- Horizon semantics: S actions change the next 2 weeks of behaviour, M actions change process or tooling, L actions change strategy, skill architecture, or standing goals. An L action with no M stepping-stone is suspect; the facilitator queries it once before accepting.

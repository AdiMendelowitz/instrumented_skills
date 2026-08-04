HANDOFF v2.0 | 2026-03-14 | supersedes: HANDOFF-2026-03-10 | session-length: medium
OBJ: ship the CSV export feature on the reporting dashboard, then start on the async job queue for large exports

STATE
  src/reports/export.py | 210L | CSV export for datasets under 10k rows, no queue
  src/reports/routes.py | added POST /api/reports/export, returns 200 with inline file
  tests/test_export.py | 14 tests, all passing, covers empty dataset and header-escaping
  docs/api.md | export endpoint documented, large-dataset behavior not yet documented

DECIDED
  exports over 10k rows return 413 for now rather than timing out silently
  CSV escaping follows RFC 4180, not Excel's looser dialect
  queue work is a separate feature, not bundled into this release

CONSTRAINTS
  no new background-worker infrastructure until the ops team approves a queue backend
  export must stream, not buffer the full file in memory, once the row cap is lifted

PROPOSED
  Redis-backed queue for exports over the row cap, with a polling endpoint for status
  moving the row cap from a hard 413 to a soft warning once streaming lands

REJECTED
  synchronous large exports with a longer timeout | ops flagged worker starvation risk
  client-side CSV generation | dataset too large for a reasonable browser memory footprint

OPEN
  which queue backend ops will approve | blocks: sizing the async work at all
  does the frontend need a progress bar for large exports | blocks: scope of PROPOSED item 1

UNVERIFIED
  assumption that all current export consumers can tolerate a 413 instead of a timeout,
  never confirmed with the two known API consumers outside the dashboard itself

PATTERN
  CSV escaping edge cases (embedded commas, quotes, newlines) found late in review twice
  now | occurrences: 2

FIRST
  Message the ops team to ask which queue backend (Redis, SQS, or an existing internal
  option) is approved for this project, since that answer blocks sizing the async work
  and nothing else in PROPOSED can move until it's known.

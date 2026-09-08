HANDOFF v3.0 | 2026-03-14 | supersedes: none | session-length: short
OBJ: ship the CSV export feature on the reporting dashboard, then start the async job queue for large exports

STATE
  src/reports/export.py | v3 | 210L 5340B | CSV export for datasets under 10k rows
  src/reports/routes.py | v2 | 84L 2110B | POST /api/reports/export endpoint
  pandas | 2.2.1 | installed in venv
  export-worker | stopped | not yet built, queue work not started

DECIDED
  exports over 10k rows return 413 for now rather than timing out silently
  CSV escaping follows RFC 4180, not Excel's looser dialect
  queue work is a separate feature, not bundled into this release

PROPOSED
  Redis-backed queue for exports over the row cap, with a polling status endpoint
  moving the row cap from a hard 413 to a soft warning once streaming lands

REJECTED
  synchronous large exports with a longer timeout | worker starvation risk
  client-side CSV generation | dataset too large for browser memory

OPEN
  which queue backend ops will approve | blocks: sizing the async work
  does the frontend need a progress bar | blocks: scope of PROPOSED item 1

UNVERIFIED
  all export consumers can tolerate a 413 instead of a timeout | never confirmed with the two known API consumers outside the dashboard

PATTERN
  CSV escaping edge cases found late in review | occurrences: 2

FIRST
  message the ops team to ask which queue backend is approved, since that blocks sizing the async work and nothing else in PROPOSED can move until it's known

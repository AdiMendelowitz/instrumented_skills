---
name: handoff
description: Write a state snapshot at the end of a session so the next conversation resumes with full context instead of a transcript summary. Separates decisions from suggestions, records recurring corrections, carries unverified claims forward, and hands off to a review/critique skill for follow-up.
argument-hint: [next-objective]
disable-model-invocation: true
allowed-tools: Read Glob Bash(wc *) Bash(python *) Bash(python3 *)
---

PROTOCOL: handoff v3.0
OBJECTIVE: $ARGUMENTS

Write a state snapshot for the next conversation. This is a resumption artifact, not a
summary. Optimize for the next session acting correctly on turn one.

This skill has no file-write access: the finished snapshot is this response's text, not
a saved file. Paste it as the first message of the next session, or save it yourself
under a name you can cite in `supersedes` later. The restatement rule under Rules is what
fires once that pasted text lands in the next session's context.

## Format

Labeled lines, not paragraphs. No markdown headers, no bullets, no connective prose. One
fact per line, pipe-delimited fields, noun phrases over sentences. Sentences appear only
where a decision turned on specific wording, in which case quote the user directly. Omit
an empty section rather than padding it. Estimated 30 to 40 percent fewer tokens than
prose for the same content; unmeasured. See `tools/measure_savings.py --compare` to turn
this into a measured figure against your own real snapshots, and replace this sentence
with the result once you have one.

```
HANDOFF v3.0 | <date> | supersedes: <prior handoff id or none> | session-length: <short|long>
OBJ: <next objective, one line>
STATE            <=8 lines, paths first, then installs, then running processes
  <path> | v<x> | <n>L <n>B | <purpose, 6 words max>
  <package/tool> | <version or commit> | installed <where>
  <process/service> | <status: running|stopped> | <what it's for, 6 words max>
DECIDED          <=10 lines, user's explicit choices only, no reasoning
  <decision>
PROPOSED         <=6 lines, assistant recommendations not yet accepted
  <item> | origin-uncertain (only when genuinely unclear)
REJECTED         <=5 lines
  <item> | <reason, 5 words max>
OPEN             <=5 lines, ranked by what blocks OBJ
  <question> | blocks: <what>
UNVERIFIED       <=5 lines
  <claim> | <why unmeasured>
PATTERN          <=3 lines, corrections that recurred this session
  <correction> | occurrences: <n>
FIRST            1 line
  <single executable action>
```

## Rules

- DECIDED holds only what the user explicitly chose. A positive reaction without a
  commitment is PROPOSED. Genuinely unclear origin goes to PROPOSED marked
  origin-uncertain; fail toward under-claiming.
- STATE lines carry line and byte counts so the next session can detect that a file
  changed after the snapshot was written. Compute them; do not estimate. Pipe the path
  through `wc -l` / `wc -c`, or use `tools/measure_savings.py --state-check` if the
  toolkit is installed, rather than reading a stale count off memory.
- supersedes names the prior handoff and voids it. Never append to an old snapshot.
- session-length is long when the session ran past roughly 30 turns. On long, add one
  line to UNVERIFIED stating the snapshot was authored under context degradation and may
  have dropped early decisions.
- PATTERN records process corrections that happened more than once, not content. Read
  `${CLAUDE_PROJECT_DIR}/.claude/critique-log/*.jsonl` if present and add any defect
  appearing in two or more runs. Where a retrospective journal exists, read it for the
  same slug as a second recurrence source: it records friction and corrections a review
  log never sees, and both already exist, so neither costs a new capture step. Absent
  both, use the session alone.
- FIRST must be executable without a clarifying question. If it is not, the snapshot
  failed to transfer enough state; revise before finishing.
- Prefer writing the snapshot before the session's final turns. Recall is worst exactly
  where this protocol is usually invoked, so a snapshot written around two-thirds through
  and updated at close beats one authored entirely at the end. Where a session-length
  hook is installed (`tools/session_watch.py`), its first nudge is the cue.
- On resumption, the next session restates STATE and OBJ in its own words before acting,
  and asks about any line it cannot ground. A snapshot that reads coherently but transfers
  nothing fails silently otherwise, and the restatement is what surfaces it on turn one
  rather than three turns into the wrong work.
- Then run a review/critique skill on the snapshot with its purpose set to OBJ, and if
  that skill supports forcing a specific lens into its selection (see its own protocol
  for how), request its archivist-equivalent lens explicitly rather than leaving lens
  selection to defaults: a snapshot benefits more from "could a stranger reconstruct
  this" scrutiny than from most other lenses. Apply SEV1 and SEV2, list SEV3 as backlog.
  Do not restate review criteria here.
- Close with at most 3 items the user has not raised, ranked, one line each with the
  cost of acting on it.

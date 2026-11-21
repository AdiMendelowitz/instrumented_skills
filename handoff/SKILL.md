---
name: handoff
description: "State snapshot at session end so the next conversation resumes with full context: decisions separated from suggestions, recurring corrections, unverified claims carried forward. Use for handoff or resume-later requests."
argument-hint: [next-objective]
allowed-tools: Read Write Glob Bash(wc *)
---

PROTOCOL: handoff v3.4
OBJECTIVE: $ARGUMENTS

Write a state snapshot for the next conversation. This is a resumption artifact, not a
summary. Optimize for the next session acting correctly on turn one.

## Format

Labeled lines, not paragraphs. No markdown headers, no bullets, no connective prose. One
fact per line, pipe-delimited fields, noun phrases over sentences. Sentences appear only
where a decision turned on specific wording, in which case quote the user directly. Omit
an empty section rather than padding it. Estimated 30 to 40 percent fewer tokens than
prose for the same content; unmeasured: see `tools/measure_savings.py --compare` to turn
this into a measured figure against your own real snapshots, and replace this sentence
with the result once you have one.

```
HANDOFF v3.4 | <date> | supersedes: <prior handoff id or none> | session-length: <short|long>
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

- Write: the snapshot goes to `<notes-root>/handoffs/handoff-v<n+1>.md`, n being the
  highest number already in that folder (list it; do not recall it), delivered per
  Destinations below; `.claude/handoff/` is not a destination on any surface.
- DECIDED holds only what the user explicitly chose. A positive reaction without a
  commitment is PROPOSED. Genuinely unclear origin goes to PROPOSED marked
  origin-uncertain; fail toward under-claiming.
- STATE lines carry line and byte counts so the next session can detect that a file
  changed after the snapshot was written. Compute them; do not estimate: pipe the path
  through `wc -l` / `wc -c`, or use `tools/measure_savings.py --state-check` if the
  toolkit is installed, rather than reading a stale count off memory. Without a shell,
  take line counts from Read's line numbers and byte sizes from the folder listing,
  labelled estimated.
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
- Next-session prompt: when the project holds `<notes-root>/prompts/SESSION_PROMPT_SKELETON.md`,
  instantiate the next session's prompt from it, filling every field or writing it as
  `not applicable: <reason>`, never by copying or patching the previous prompt. Write it to
  `<notes-root>/prompts/` per Destinations rule 3, name it in FIRST, and run the critique
  skill on it with the snapshot's OBJ as purpose.
- Prefer writing the snapshot before the session's final turns. Recall is worst exactly
  where this protocol is usually invoked, so a snapshot written around two-thirds through
  and updated at close beats one authored entirely at the end. Where a session-length
  hook is installed (`tools/session_watch.py`), its first nudge is the cue.
- On resumption, the next session restates STATE, OBJ, and OPEN in its own words before acting,
  and asks about any line it cannot ground. A snapshot that reads coherently but transfers
  nothing fails silently otherwise, and the restatement is what surfaces it on turn one
  rather than three turns into the wrong work.
- Then run a review/critique skill on the snapshot with its purpose set to OBJ, and if
  that skill supports forcing a specific lens into its selection (see its own protocol
  for how), request its archivist lens explicitly rather than leaving lens selection to
  defaults, since a snapshot benefits more from "could a stranger reconstruct this"
  scrutiny than from most other lenses. Apply SEV1 and SEV2, list SEV3 as backlog. Do not
  restate review criteria here.
- Also invoke `retrospective`'s LITE mode on this snapshot when a paired `retrospective`
  skill is installed and either PATTERN is non-empty or a `.claude/critique-log/` entry
  for this target shows a finding recurring across two or more runs: these are the two
  signals `retrospective`'s own trigger test names. Pass the slug this handoff resolved
  to under Destinations rule 3. Skip in one line, naming which signal was absent, when
  neither fires.
- Close with at most 3 items the user has not raised, ranked, one line each with the
  cost of acting on it.

## Destinations (DESTINATIONS v1; full text inline, since the account copy ships as SKILL.md only and has no `../DESTINATIONS.md`)

1. Resolve the write target from the project CLAUDE.md section "Where internal files live"
   (in Cowork, stage the project's CLAUDE.md to read it). If absent: notes root is
   `data/notes/` when `data/` is gitignored, else `notes/`; ask one question, then write
   `<notes-root>/README.md` and the CLAUDE.md block and hand over the `.gitignore` line.
   Never a folder named after a tool, never "Claude outputs".
2. Skill state (`actions.jsonl`, the journal, critique-log lines) is canonical under `.claude/`.
   On local Claude Code, write it there directly. On the Cowork device bridge `.claude/` is
   unreachable: never attempt or propose a `.claude/` write there, not even as a command handed
   to the user. Stage the lines at `<notes-root>/prepared/pending-<kind>-<date>.jsonl` and
   report "staged, not landed" with the expected post-append line count. That staged file is
   the final resting place on Cowork, not a step toward a later `.claude/` write.
3. Documents: retro to `<notes-root>/retros/`, handoff to `<notes-root>/handoffs/`, session
   prompt to `<notes-root>/prompts/`, filename per the project table, else the skill's own
   default. A copy under `.claude/` is byte-identical or absent (on Cowork, absent, per rule
   2). A critique patch stays beside its target.
4. Delivery to a connected folder: write under `/mnt/user-data/outputs/`, commit with
   `device_commit_files` (`stagedPath` plus the exact `devicePath`), then re-stage and compare
   md5. Never `SendUserFile` while any folder is connected. `written: true` is not evidence.
5. No folder connected: write to the attached Project's docs as `claude/<same basename>`.
   With a folder connected, the device copy is the original and the Project doc a mirror.
6. Shell down (`no Plan9 drive shares mounted`): reads via `device_stage_files`, counts from
   Read line numbers labelled estimated, shell-only steps marked UNKNOWN and handed over as
   PowerShell 5.1, one command per line, marked untested. Local Claude Code has no bridge
   and no `SendUserFile`: write to the resolved path and read it back.

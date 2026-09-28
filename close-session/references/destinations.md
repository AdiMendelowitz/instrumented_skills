# Destinations (DESTINATIONS v1)

Identical across `retrospective`, `critique`, `handoff`, and `close-session`. Each of those
`SKILL.md` files carries a short inline summary of rules 1 to 3 (the common path) and
points here for the rest, including the two Cowork-specific edge cases (4 and 6).

1. Resolve the write target from the project CLAUDE.md section "Where internal files live"
   (in Cowork, stage the project's CLAUDE.md to read it). If absent: notes root is
   `data/notes/` when `data/` is gitignored, else `notes/`; ask one question, then write
   `<notes-root>/README.md` and the CLAUDE.md block and hand over the `.gitignore` line.
   Never a folder named after a tool, never "Claude outputs".
2. Skill state (`actions.jsonl`, the journal, critique-log lines) is canonical under `.claude/`.
   Attempt that write first on a surface with real shell access to `.claude/` (Claude Code, a
   local terminal). On the Cowork device bridge, `.claude/` writes are refused ("Writing to
   .claude is not permitted via remote tools") and MUST NOT be attempted or proposed there,
   including as a manual command handed to the user: stage the lines instead at
   `<notes-root>/prepared/pending-<kind>-<date>.jsonl` and report "staged, not landed" with
   the expected post-append line count. That staged file is the final resting place on
   Cowork, not a step toward a later `.claude/` write. (Corrected 2026-09-14: the previous
   wording of this rule told Cowork sessions to hand over a `.claude/` append command after
   staging; that recurred as the exact behaviour the user had already asked to stop.)
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

# instrumented_skills

## Where internal files live

All session files are gitignored under `blog/notes/`, one folder per kind;
`blog/notes/README.md` carries the full table. `/retrospective`, `/critique`,
`/handoff` and `close-session` write their human-readable outputs to these
paths on every surface (Claude Code, Cowork, claude.ai), not to a folder named
after the tool and never to a "Claude outputs" folder; the destination is agreed
here, so no skill needs to ask.

| Kind | Path |
|---|---|
| Session-open prompts | `blog/notes/prompts/next-session-prompt-<date>.md` |
| Handoffs | `blog/notes/handoffs/HANDOFF-<date>.md` (latest date is current) |
| Session retrospectives, their patches and audits | `blog/notes/retros/retrospective-<date>-<slug>.md`, `.v<n>-patch.md` |
| Day plans | `blog/notes/plans/plan-<date>.md` |
| Shell-down bridge notes | `blog/notes/bridge/bridge-check-<date>T<hhmm>Z.md` |
| Staged work the bridge cannot land (pending journal and action lines, patches, scripts) | `blog/notes/prepared/` |

Skill state stays in `.claude/retro-log/` and `.claude/critique-log/`; `.claude/handoff/`
is not a destination. The Cowork bridge cannot write under `.claude/`: state lines it
cannot land go to `blog/notes/prepared/pending-*.jsonl` for a PowerShell append; a retro
copied into `.claude/retro-log/retros/` is byte-identical to the one in `blog/notes/retros/`.

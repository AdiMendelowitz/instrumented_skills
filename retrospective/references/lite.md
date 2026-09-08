# Bundle: lite

Bounded mini-retro invoked from /critique or /handoff. Total cost: the trigger test, at most 2 reads beyond files already in context, ≤ 12 journal lines, ≤ 1 action line. Never open RUN machinery, never write a retro document, never convene the panel.

## Trigger test (the judgement call)

Run LITE only when at least 2 of the following hold; otherwise decline silently and let the caller finish normally:

1. The journal for the slug has 5 or more lines with a `ts` in the last 14 days. Bare existence does not count: the capture hook creates journals for nearly every project, so existence alone carries no signal.
2. The caller is /handoff and its PATTERN section is non-empty, or session-length is long.
3. The caller is /critique and its log for this target shows the same finding id STILL-PRESENT across 2+ runs.
4. The target belongs to a tracked project (slug resolvable to a project directory), rather than a standalone file.
5. The user asked for lessons or a retro in this session.

Hard exclusions, overriding the count: a stateless one-off script or document reviewed for the first time; a pure formatting or cosmetic pass; SELF mode in /critique.

Condition 3 exists because a defect that survives a review cycle is a process problem wearing a code problem's clothes; that is retrospective territory, where a first-sighting defect is critique territory alone.

## Protocol

1. Slug: derive from the caller's target path or the project directory name.
2. Write journal lines, schema per SKILL.md, capped at 12 total:
   - from /critique: one `result` line per SEV1-2 finding class (not per finding), one `friction` line per STILL-PRESENT recurrence naming the run count, one `win` line if the run was clean or a prior finding resolved.
   - from /handoff: one `decision` line per DECIDED item not yet journalled, `expect` filled from the session's stated intent; one `friction` line per PATTERN entry with its occurrence count; one `event` line for the OBJ.
3. At most one action, and only when a recurrence (critique) or a 2+ occurrence pattern (handoff) is present. Horizon S, owner set (defaulting to the user), due date set, appended to `actions.jsonl`. First-time observations never generate actions; they wait for a full retro.
4. Report to the caller in one line: `LITE: <n> journal lines, <0|1> action, slug <slug>` (or `LITE: declined, <reason in 4 words>`). The caller embeds this line in its own output and continues.

## Integration lines for the callers

Proposed additions, delivered as diffs for approval per house convention:

/critique, end of P7, after the log append:
`Then run the LITE trigger test in ~/.claude/skills/retrospective/references/lite.md (%USERPROFILE%\.claude\skills\... on Windows); on pass, execute LITE and embed its one-line report before the closing weakest-part line.`

/handoff, in Rules, after the /critique handoff line:
`After the critique pass, run the LITE trigger test in ~/.claude/skills/retrospective/references/lite.md (%USERPROFILE%\.claude\skills\... on Windows); on pass, execute LITE so decisions and patterns reach the retro journal, and embed its one-line report.`

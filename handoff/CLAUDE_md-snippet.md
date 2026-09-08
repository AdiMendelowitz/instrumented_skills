# CLAUDE.md snippet: session-length coordination

Two halves. The hook counts turns and states the count as a fact. This snippet tells
Claude what to do about that fact. The split is deliberate and matches Anthropic's own
guidance: dynamic environment state belongs in a hook, static instructions belong in
`CLAUDE.md`, and hook text phrased as an out-of-band command can trip prompt-injection
defenses and get surfaced to you instead of acted on.

## 1. The CLAUDE.md text

Paste into `~/.claude/CLAUDE.md` (or a project's `CLAUDE.md`):

```markdown
## Session length

A "Session state:" line reporting a user-turn count may appear in context. It is
injected by a hook that counts turns deterministically, not something I typed.

- First one (turn count "approaching" the threshold): at the next natural break, say
  once that the session is getting long and that running `/handoff` and continuing in
  a fresh session would be worth doing soon. Do not interrupt work in progress, and
  do not raise it again.
- Second one (count reported as making early detail "materially less reliable"):
  say plainly that the session is long enough that early decisions are unreliable,
  recommend running `/handoff` now, and note a later snapshot will capture less.
- If I decline either time, continue normally and drop it for the session.
- When I do run `/handoff`, treat UNVERIFIED as mandatory: any fact established early
  in the session and not rechecked since belongs there.
```

## 2. Registering the hook

Copy `session_watch.py` to `~/.claude/skills/handoff/tools/`, then add to
`~/.claude/settings.json`. If you already run hooks (a `Stop` hook for journal capture,
say), add this alongside them rather than replacing the `hooks` object: entries merge
across settings levels.

**Use an absolute path.** A bare `~` is expanded by `sh` and Git Bash but not by
PowerShell, which is what Claude Code uses on Windows when Git Bash isn't installed, so
a `~/...` command silently fails there. Exec form (`command` + `args`) is also preferred
over shell form: each argument passes through verbatim with no shell tokenization, so
paths containing spaces need no quoting.

macOS / Linux:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3",
            "args": ["/Users/you/.claude/skills/handoff/tools/session_watch.py"],
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

Windows: point `command` at a real `python.exe`, since a bare `python` can resolve to
the Microsoft Store stub, which produces no output and no error:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "C:\\Users\\you\\AppData\\Local\\Programs\\Python\\Python312\\python.exe",
            "args": ["C:\\Users\\you\\.claude\\skills\\handoff\\tools\\session_watch.py"],
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

The explicit `timeout: 10` is below this event's 30-second default. `UserPromptSubmit`
blocks model processing while it runs, so a lower ceiling means a pathological case
costs you ten seconds rather than thirty. Measured cost on a 10 MB, 300-turn transcript
is under 0.1 s, and the hook exits without reading the transcript at all once its last
threshold has fired.

## 3. Tuning

| Variable | Default | Effect |
|---|---|---|
| `HANDOFF_WARN_TURNS` | 25 | first, soft signal |
| `HANDOFF_URGE_TURNS` | 35 | second, direct signal |
| `HANDOFF_WATCH` | unset | set to `0` to disable without unregistering |
| `HANDOFF_WATCH_STATE` | `~/.claude/handoff-watch` | where firing markers live |

Defaults bracket the `session-length: long` threshold in `SKILL.md` (roughly 30 turns),
so the first signal arrives with room to act and the second arrives once the protocol
would already class the session as long. Both fire at most once per session.

## 4. Verifying it works

The hook is silent until a threshold is crossed, which makes "installed correctly" and
"installed and broken" indistinguishable for the first 25 turns. A journal-capture hook
in a companion skill failed silently for weeks in this project's own history and was
noticed only when an unrelated file showed a stale date. Check explicitly:

```bash
echo '{"transcript_path":"/path/to/any/transcript.jsonl","session_id":"test"}' \
  | HANDOFF_WARN_TURNS=1 python3 ~/.claude/skills/handoff/tools/session_watch.py
```

Transcripts live under `~/.claude/projects/<project-slug>/*.jsonl`; any real one works.

Expected: one plain-text line beginning `Session state:`. Empty output with exit code 0
means the transcript path was wrong or held no countable user turns. The hook fails open
by design so it can never block a prompt, and that same property is what allows silent
failure, so re-run this check after any Python upgrade, settings edit, or path change.

## Known behavior worth expecting

- **The count is a floor.** Claude Code writes the transcript asynchronously, so it can
  lag the live conversation by a turn or two. Messages say "at least" for this reason.
- **Resumed sessions replay, they don't recount.** On `--resume` or `--continue`, Claude
  Code replays previously injected hook text rather than re-running the hook for past
  turns, so an old count may reappear. The marker files prevent a duplicate live firing.
- **Tool results don't count.** They're recorded with `type: "user"` in transcripts;
  counting them would fire the signal several times early on tool-heavy sessions.

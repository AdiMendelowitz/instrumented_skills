# close-session

**End a session with a record the next one can act on from its first turn.**

`close-session` runs four phases, and each phase's output is the next one's only input: an
adversarial retrospective, a critique of that retrospective to convergence, an independent
verification pass that writes the structured handoff, and the next session's opening prompt
in a step-numbered shape that a session with no memory of this one can execute.

| | |
|---|---|
| Protocol | v1.14, phases 1 to 4, one shared cap of two convergence rounds |
| Run it with | `/close-session` |
| Works with | `retrospective`, `critique` and `handoff`; where one is missing, that phase runs inline at reduced quality and the close says so |
| Toolkit | none of its own; the handoff checks use `handoff/tools/measure_savings.py`, so install `handoff` for them |
| Writes | the retro, the patched retro, the handoff and the session-start prompt, to `retros/`, `handoffs/` and `prompts/` in your notes folder |

## Quick start

```bash
./install.sh close-session retrospective critique handoff     # from the repo root
```

When a session is wrapping up in Claude Code, run `/close-session`. The reply is five lines
(what ran, what the retro found, what the handoff carries forward, the top risk and the
three file paths) followed by a short start message to paste as the first message of the
next session.

## Adapting this skill

Decide the notes folder first, as [Where files go](../README.md#where-files-go) describes.
Every file the skill writes is read back after writing, and a write it cannot verify is
reported as unverified.

## Files

```
SKILL.md                             the protocol: environment detection, budget, four phases, save and verify, the close
references/design-rationale.md       the evidence behind each choice, for when a rule looks unmotivated
references/session-start-template.md the shape of the Phase 4 prompt
evals/evals.json                     three regression cases, fixtures in evals/fixtures/
evals/results-2026-10.md             one run per case, with and without the skill, on an earlier version
```

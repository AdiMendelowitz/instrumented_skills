# close-session

**End a session with a record the next one can act on from its first turn.**

Four phases, each one's output the next one's only input: an adversarial retrospective, a
critique of that retrospective to convergence, an independent verification pass that writes
the structured handoff, and the literal first message of the next session, in a STEP-numbered
shape a session with zero memory of this one can execute.

| | |
|---|---|
| **Protocol** | v1.7, phases 1 to 4, one shared 2-round convergence cap |
| **Companions** | `retrospective`, `critique`, `handoff` (each phase runs its companion's protocol; where one is missing, the phase runs its shape inline and says so) |
| **Toolkit** | none; the checks it needs live in `handoff/tools/measure_savings.py` |
| **Writes** | retro, patched retro, handoff and session-start prompt to the project's `<notes-root>/{retros,handoffs,prompts}/`, per the DESTINATIONS block shared with the three companions |

## Files

- **`SKILL.md`**: the protocol. Environment detection, budget, the four phases, the save-and-verify rule, the 5-line close.
- **`references/design-rationale.md`**: the evidence behind the choices, read once if a rule looks unmotivated.
- **`references/session-start-template.md`**: the shape of the Phase 4 prompt.

## Adapting this skill

The one setting to decide up front is the notes root: the folder your project's `CLAUDE.md`
names under "Where internal files live". Without it the skill asks once, then bootstraps
`notes/` (or `data/notes/` when `data/` is gitignored). The Cowork-specific delivery rules in
the DESTINATIONS block (`device_commit_files`, md5 read-back) apply only on that surface;
local Claude Code writes to the resolved path and reads it back.

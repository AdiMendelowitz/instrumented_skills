# handoff

A structured end-of-session state snapshot, in place of a prose "here's where we left
off" recap. The schema exists because prose doesn't force you to separate a decision you
made from a suggestion you reacted well to — a few sessions later, those read the same,
and a plan you never actually committed to starts getting treated as settled.

## ⚠️ Note on this file

`SKILL.md` here is a **reconstruction**, built from a fully worked example of this
skill's output rather than from the original protocol file itself (which wasn't
available when this repo was scaffolded). The schema and field semantics match the
example closely; the exact wording of the rules is a best-effort draft. Read it, adjust
it to how you actually want it to behave, and don't assume it's verbatim anyone's
original. `example-handoff.md` is a sanitized worked example so you can see the schema
in use before writing your own real one.

## The schema

```
STATE          verifiable facts about the artifacts — paths, versions, counts
DECIDED        things actually committed to (high bar — a liked suggestion isn't a decision)
CONSTRAINTS    hard limits the next session's work must respect
PROPOSED       suggestions on the table, not yet committed
REJECTED       options considered and dropped, with why
OPEN           questions blocking a specific next step, naming what they block
UNVERIFIED     claims carried forward that were never independently rechecked
PATTERN        recurring issues, with an occurrence count
FIRST          the exact next action — singular, specific enough to execute directly
```

## Why this shape

**DECIDED vs. PROPOSED** is the distinction that does the most work. It's tempting to
write "we're doing X" the moment an idea lands well in conversation, but that collapses
two different things: a firm commitment, and an option that was well-received. Keeping
them in separate sections means a future session (or a future you) can tell which is
which without re-reading the whole conversation for tone.

**UNVERIFIED** exists for long sessions specifically. Facts established early in a long
conversation get less reliable as the conversation goes on — not because anyone's being
careless, but because context degrades. This section is where a carried-forward claim
gets flagged as carried-forward, instead of silently being restated as current fact in
the next handoff.

**PATTERN** is what makes handoffs additive across a project instead of each one
starting cold. An issue that shows up once is a note. The same issue showing up in three
consecutive handoffs is a pattern worth acting on differently, and the occurrence count
is what makes that visible without you having to remember it yourself.

## Adapting this skill

The nine sections are a strong default, not a fixed requirement — if your work doesn't
produce REJECTED-worthy decisions often, for instance, you can leave that section
consistently `none` without removing it from the schema (consistency across handoffs
matters more than trimming unused sections). If you pair this with a review or critique
skill, the "Handoff to review" section in `SKILL.md` is the connection point — it flags
when a review pass is due without performing one itself, so the two skills stay
decoupled.

## Files

```
SKILL.md              the protocol (reconstructed — see the warning above)
example-handoff.md    a sanitized worked example for a generic web app project
```

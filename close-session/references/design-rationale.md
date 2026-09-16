# Bundle: design-rationale

Not needed to execute the skill. Read this once if a rule in SKILL.md needs its evidence, or
before editing SKILL.md, so a future edit doesn't quietly undo a fix that was earned the hard
way. Every claim below is anchored to something that actually happened, not a general worry.

## Why self-doubt framing was replaced with an actual fork

Telling a model to "assume you missed something and check harder" sounds like it should work,
and twice in this project's own history it didn't: a self-review pass cleared its own compliance
gate while having fabricated a word-count figure and skipped half its prior-action
reconciliation. A forked, independently-primed second pass, given the same material but not the
same drafting context, caught both in one run. The mechanism that works is structural
independence, not a stronger instruction to the same context. That's why Phase 3 forks rather
than re-asking.

## Why every convergence loop shares one 2-round cap

The four raw instructions this skill was built from each said "repeat until resolved" or
equivalent, with no stated stopping point, in three separate places. `critique` and
`retrospective` already run tiered, budgeted passes; stacking an uncapped loop on top of an
already-capped protocol multiplies cost without a matching return past the second pass, and
directly works against the token-efficiency goal that motivated building this skill at all. One
shared cap, stated once, is cheaper to reason about than three separately-worded unbounded
instructions.

## Why storage target gets chosen before anything is written

Four consecutive retrospectives in this project logged their own action-tracking as
"functionally decorative" because the environment running them (Cowork, no local filesystem)
couldn't reach the path the protocol assumed (`.claude/retro-log/`). A retrospective or handoff
that has nowhere agreed to land ends up readable only inside the document that produced it,
which defeats the entire point of writing it for a future session to pick up.

## Why "hostile" doesn't appear in the instructions

`critique`'s own `docs.md` bundle names "hostile" specifically as jargon that steers a model
toward theatrical aggression rather than calibrated rigor. The underlying finding, that an
independent pass catches what self-review misses, is real and stays real; only the word changed,
to "independent verification pass."

## Why Phase 3 writes the handoff instead of running another retrospective

A retrospective analyses a period; a handoff transfers state to the next session. Collapsing
those into one document, or running a second full retro pass where a state-transfer document
would do, has already caused real confusion in this project: an old handoff carried enough
analysis inside it that nobody could later tell whether a line was a decision the user made or a
suggestion Claude offered that landed well. Keeping the roles distinct is what makes the
DECIDED/PROPOSED split in the handoff schema actually mean something.

## Why file paths get verified before Phase 4 prints them

A file "produced" in one part of a session isn't confirmed to exist until it's read back from an
absolute path; a prior session in this project treated a staged, unconfirmed file as installed
and built on that assumption for several turns before the gap surfaced. Phase 4 is the last
phase before a fresh session inherits this one's claims wholesale, so it's the cheapest place to
catch a dead path, and the most expensive place to miss one.

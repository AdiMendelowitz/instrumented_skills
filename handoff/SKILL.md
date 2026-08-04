---
name: handoff
description: Write a state snapshot at the end of a session so the next conversation resumes with full context instead of a transcript summary. Separates decisions from suggestions, records recurring corrections, carries unverified claims forward, and hands off to a review/critique skill for follow-up.
argument-hint: [optional: session-length hint]
---

<!--
NOTE: this SKILL.md is a reconstruction, not the verbatim original. The source project
files available when this repo was scaffolded included a fully worked *example* of this
skill's output (a real handoff document) but not the protocol file itself. The schema and
field semantics below are reverse-engineered from that example and from how it was
described elsewhere in the source material. Read it, adjust wording to taste, and treat
it as a strong starting draft rather than a faithful copy of anyone's original.
-->

## Why a schema instead of a summary

A prose recap of a session reads as complete and often isn't: it doesn't force a
separation between something you actually decided and something you reacted well to when
it was offered, and a few sessions later those read identically. It also has no natural
place for "I established this fact forty turns ago and haven't rechecked it since,"
which matters once a session runs long enough that early context degrades. The schema
below exists to make both of those distinctions structural rather than optional.

PROTOCOL: handoff
CONTEXT-HINT: $0 if supplied (e.g. "long", "short"), else infer from the session.

## Contract

Deliver one document, pipe- or colon-delimited by section, no prose framing before or
after it. Header line first: `HANDOFF v<n> | <date> | supersedes: <prior handoff id, or
"none"> | session-length: <short|medium|long>`.

Then, in this order, every section present even if empty (mark an empty section
`none`):

```
STATE         current, verifiable facts about the artifacts themselves — file paths,
              versions, line/byte counts, what's installed where. Not what you believe
              is true; what you can point to.
DECIDED       things actually committed to. The bar for landing here is high: a
              suggestion the person reacted well to is not a decision. Only what was
              explicitly chosen goes here.
CONSTRAINTS   hard limits on the solution space — technical, organizational, or
              personal — that any future work in this context must respect.
PROPOSED      suggestions on the table, not yet committed. Where an idea originated as
              a proposal and the person hasn't explicitly confirmed it, it stays here
              even after several sessions, rather than migrating to DECIDED by drift.
REJECTED      options considered and explicitly dropped, one line each on why, so a
              future session doesn't re-propose something already ruled out.
OPEN          questions that block a specific next step. Each one names what it
              blocks, not just that it's unresolved.
UNVERIFIED    claims carried forward from earlier in the session (or from a prior
              handoff) that were never independently checked. This section exists
              specifically to survive context degradation: facts established forty
              turns ago in a long session get fuzzy, and this is where "this was true
              earlier, I haven't rechecked it" lives instead of being restated as
              settled fact.
PATTERN       recurring issues or corrections, each with an occurrence count. A thing
              that's happened once is a note; a thing that's happened three times
              across sessions is a pattern, and the count is what makes that visible.
FIRST         the exact next action. Specific enough that the next session can execute
              it without re-reading the rest of the handoff first.
```

## Rules

- **Decision vs. suggestion is the load-bearing distinction.** Before writing anything
  into DECIDED, check: did the person explicitly commit to this, or did they react
  positively to something offered? A positive reaction to a proposal is not a decision.
  When in doubt, it goes in PROPOSED.
- **STATE is for facts you can currently verify**, not facts you established at some
  earlier point in the session and are assuming still hold. Where a STATE-like fact
  hasn't been rechecked recently, it belongs in UNVERIFIED instead.
- **PATTERN entries need an occurrence count**, not just a description. "The installer
  script has shipped with a defect twice" is a pattern; "the installer script had a bug"
  is a one-off note and doesn't belong in this section.
- **FIRST is singular.** One action, not a list of options. If there's real ambiguity
  about what to do next, that ambiguity itself belongs in OPEN, and FIRST names the
  smallest action that would resolve it.
- **This document supersedes prose summaries for continuity purposes.** Where this skill
  is available, prefer writing a handoff over a free-text "here's where we left off"
  recap — the schema exists specifically because prose lets a decision and a suggestion
  read identically a few sessions later.

## Handoff to review

Where a review or critique skill is available in the same environment, a session ending
with unresolved SEV1/SEV2-equivalent issues in PATTERN or OPEN should note that a review
pass is warranted, rather than silently deferring it. This skill does not perform the
review itself — it only flags that one may be due.

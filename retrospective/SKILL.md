---
name: retrospective
description: Structured retrospective on any project, task, or session. Continuous journal capture (LOG mode) feeds panel-based retros (RUN mode) at three tiers, from a short mini-retro to a full multi-persona debate with a facilitator. Produces a consolidated document with decision review, insights, and owned actions on short, medium, and long horizons, plus proposed changes to skills and configs. Use for retro, retrospective, post-mortem, after-action review, lessons learned, "what did we learn", weekly review, or project wrap-up requests. Also invoked at reduced scale (LITE) by paired skills when their own trigger test passes.
---

# Retrospective | v1.0 | template

PURPOSE: turn recurring work into a record that compounds, rather than a fresh "lessons
learned" every time. A retro that doesn't reference the last one on the same slug is a
diary entry, not a retrospective. This skill's two modes exist specifically to make the
reference automatic instead of dependent on memory.

## LOG mode

Continuous, lightweight journal capture during normal work; not a retro itself, but the
raw material RUN mode reads instead of reconstructing history from scratch. One line per
notable event: a decision made, a defect found and its resolution, a course correction
and why. Timestamped, appended, never edited after the fact: a correction gets a new
line, not a rewritten old one, so the record shows what was believed at the time.

Where the filesystem persists (a repo, a project with a config directory), the journal is
a file the project owns. Where it doesn't, it lives in memory; see this skill's README
for how to decide which projects get their own index versus a shared one.

## RUN mode, three tiers

**T1, mini-retro.** Roughly a dozen lines: what happened, what worked, what didn't, one
or two actions. No panel, no facilitator. Appropriate for a single session's wrap-up or a
small, low-stakes task.

**T2, medium retro.** A handful of lenses (pick from the standing set in
`references/panel.md`, sized to what's actually relevant), each contributing anchored
findings, synthesised without a full formal debate. Appropriate for a completed feature,
a sprint, or a moderate-stakes decision review.

**T3, full panel.** The complete facilitator protocol in `references/panel.md`: quieter
lenses sequenced before dominant ones, anchors enforced at intake, ELMO to end a thread
once it stops producing new root causes, a debate that merges convergent findings and
forces conflicting lenses to name what evidence would settle their disagreement.
Appropriate for a project close-out, a significant incident, or anywhere the cost of
missing something is high enough to justify the extra structure.

Pick a tier by stakes and scope, not by habit. A T3 panel on a routine weekly check-in
is wasted structure, and a T1 mini-retro on a project close-out under-serves the
questions that actually need a debate.

## LITE invocation

A paired skill (a review/critique tool, a handoff skill) can trigger a reduced-scale
retro automatically when its own conditions are met, for example, a review that closes
out a project, or a handoff that surfaces the same pattern for the third time. LITE means
T1-scale by default: a short capture, not a full panel, unless the triggering condition
itself signals higher stakes. This keeps retros from requiring an explicit request every
time one would actually be useful.

## Output: the consolidated document

Every RUN-mode retro, regardless of tier, produces:

```
Scope         period covered, purpose, participants/lenses used (T1: implicit; T2/T3: named)
Decision review   what was decided during the period, and whether it held up
Insights          what the lenses (or, at T1, a single pass) actually surfaced
Actions           bucketed by horizon:
                    short   do this now, before the next session
                    medium  do this within the current project/cycle
                    long    structural, worth doing but not urgent
Proposed changes  edits to skills, configs, or standing rules the retro's findings
                  suggest. Proposed, not applied: a human or a separate promotion
                  step decides whether to act on them
```

At T2/T3, the facilitator (see `references/panel.md`) owns assembling this from panel
output; the debate belongs to the panel, the synthesis belongs to the facilitator.

## Connecting to a paired review/critique skill

Where a review or critique skill's log carries structured counters (calls, findings,
whether a prior patch was promoted), the finance lens in `references/panel.md` treats
that as admissible cost evidence; see its anchoring rule for what counts and what the
fallback is when no such data exists. This is the only place retrospective depends on
another skill's output, and it degrades gracefully: without that data, the lens reports
no findings rather than guessing.

## Reference files

- `references/panel.md`: the full T3 facilitator protocol, the eight standing lenses,
  and the project-personas extension point for adding domain-specific reviewers.

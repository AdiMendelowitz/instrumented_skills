# Bundle: session-start-template

Shape for Phase 4's output. Fill every bracket from the Phase 3 handoff; do not invent a field
with no source.

```
TARGET: <environment: local Claude Code at <absolute project root>, or Cowork/claude.ai
attached to <Project name>>. Do not proceed past STEP 0 until that environment is confirmed by
a command or tool call run inside this session, not assumed from this prompt.

PURPOSE: <today's objective, one line> | DONE means: <definition of done, one line, falsifiable>

## BUDGET
Cap STEP 0 (read-in) at <n> tool calls; read every file below in one batched pass, not one
call each. Cap plan-critique at 2 rounds, converge or ship with backlog listed, no third round.
Every verification (file exists, command output, git state) is a command run and its literal
output reported, never inferred.

## STEP 0: get informed, read-only, batched
Read in one pass: <handoff path>, <patched retrospective path>, <any STATE-named files>.
Nothing above is fact until re-checked against its actual current state; a prior session's
claim a file was written is not evidence it exists.

## STEP 1: state objective and DOD
One line each, before anything else: today's objective, and what "done" looks like. If either
is unclear from STEP 0's sources, ask once rather than guessing.

## STEP 2: review what the objective touches
<code / repo / docs / config, whichever STATE names as relevant>, before planning against it
from memory or from this prompt's own summary of it.

## STEP 3: plan, ranked by ROI
Order by cheapest change that unblocks the most OPEN/PROPOSED items first, not by file-
discovery order or by the sequence this prompt lists sources in.

## STEP 4: critique the plan once, capped
Same 2-round cap as BUDGET states. Fix what it finds, then execute.

## STEP 5: print the final task list only
Ordered, each item naming the file or command it touches. No preceding narration once this
step is reached.
```

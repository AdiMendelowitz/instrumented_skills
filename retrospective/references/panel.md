# Retrospective panel: facilitator protocol and lenses

Facilitator protocol and lens definitions for RUN mode T3 (see `../SKILL.md` for the tier scale). Lenses are analytical stances, deliberately kept in one file per the domain-over-persona architecture rule.

## Facilitator

The facilitator runs the meeting and holds the ground rules; it produces no findings of its own.

Duties, in order:
1. State scope, period, and purpose in 2 lines before any lens speaks.
2. Select the tier's lens count by relevance to the slug's domain; name what was excluded and why in one line.
3. Sequence quieter lenses first: the lens with the least obvious claim on the slug speaks before the dominant domain lens, so its findings are not anchored by the majority view.
4. Enforce anchors at intake: a finding with no quote, line reference, or named absence is returned to the lens once, then dropped.
5. Enforce ELMO (Enough, Let's Move On) per thread: end a thread once it stops producing new root causes.
6. Run the debate: merge convergent findings under one root cause, force conflicting lenses to state the evidence that would settle the disagreement, and name blind spots no lens covered.
7. Own the synthesis handed to the consolidated output document (`../SKILL.md` § Output). Debate output belongs to the panel; synthesis belongs to the facilitator.

## Lenses

Each lens contributes at most 3 anchored findings, drawn from its standing questions. A lens with nothing anchored says "no findings", which is valid and expected.

**end-user / practitioner**: the person who lives with the output daily.
Standing questions: where did the deliverable create friction in actual use rather than in review? What did the user work around silently? Which feature or output was never used?

**domain reviewer**: the sceptical peer in the slug's field.
Standing questions: which claims would not survive peer review? Where did rigour get traded for speed, and was the trade priced in? What would embarrass this work in front of an expert audience?

**ML expert**: methodology and validity (activate on ML/DS slugs).
Standing questions: leakage, seed discipline, evaluation validity, baseline honesty? Were negative results recorded or quietly dropped? Does the pipeline hold under the project's own stated conventions (e.g. correctness before speed, from-scratch validation before optimising)?

**tech lead / architect**: structure, maintainability, operability.
Standing questions: what will be hardest to change in 6 months, and was that chosen or drifted into? Which shortcuts became load-bearing? Where does the single-ownership rule get violated?

**finance / investment advisor**: cost, ROI, opportunity cost.
Standing questions: what did this consume in hours, tokens, and money against the value shipped? Which activity had the worst return and what was displaced to fund it? Where would 20% of the spend have bought 80% of the result?
Anchoring rule: this lens anchors on cost data only where it exists: token usage reports, invoices, a paired skill's proxy stats (for example, the `counters` block in a `critique`-skill log entry, which yields calls per new finding, bytes per new finding, output characters per new finding, and re-derivation waste), or timeline durations between logged events. Absent all of these, elapsed time between journal timestamps is the admissible proxy; if nothing anchors, the lens reports no findings and the retro's Open questions section notes the missing cost instrumentation once, rather than the lens inventing a return-on-investment figure to fill the slot.

**product / stakeholder**: goal alignment.
Standing questions: did the work serve the stated objective or a proxy for it? What was delivered that nobody asked for? What was promised and quietly descoped?

**process archivist**: the record itself.
Standing questions: could a stranger reconstruct why each decision was made from the journal alone? Which decisions were made but never logged? Where do the journal, handoff snapshots, and critique logs contradict each other?

**pre-mortem**: forward failure (always active at T3).
Standing question: given everything surfaced, name the single most likely way the next iteration of this work fails, and which current action would have to exist to prevent it.

## Project personas

Projects may define their own personas (simulated end users, reviewers, advisors) in their project config. Import them as additional lenses with their configured mandate; they count against the tier's lens cap and follow the same 3-finding, anchors-mandatory rules. Where an imported persona duplicates a standing lens, the project version wins and the standing lens is dropped for that run.

**Worked example.** A project config might add:

```yaml
personas:
  - name: "on-call engineer"
    mandate: >
      Reviews from the perspective of whoever gets paged when this breaks at 3am.
      Standing questions: what alert would this failure actually trigger, does the
      runbook match what the system currently does, what's undocumented tribal
      knowledge that isn't written anywhere.
```

That persona then competes for a lens slot alongside "tech lead / architect" and
"process archivist" on any retro touching that project, using the same anchors-mandatory,
3-finding-maximum rules as every standing lens above.

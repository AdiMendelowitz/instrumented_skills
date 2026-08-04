# retrospective

Structured retrospectives that compound instead of restarting from zero each time — a
fixed panel of lenses, each required to anchor its findings in something real, plus a
facilitator that sequences quieter perspectives before the dominant one so early findings
don't anchor everything that follows.

## Note on this skill

`SKILL.md` defines LOG mode (continuous journal capture), the three RUN-mode tiers
(mini-retro up to full panel), the LITE auto-invocation path from paired skills, and the
shape of the consolidated output document. `references/panel.md` is the detailed
facilitator protocol and lens set that the full T3 tier in `SKILL.md` calls out to.
Nothing here is a placeholder; adapt tier boundaries, lens selection, or the output
schema to taste using the guidance below.

## What `panel.md` gives you, ready to use

- A facilitator role that runs the meeting, sequences lenses (quietest first, so it
  doesn't anchor on the loudest), and owns synthesizing the debate into output — but
  contributes no findings of its own.
- Eight standing lenses (end-user, domain reviewer, ML expert, tech lead, finance,
  product, process archivist, pre-mortem), each capped at 3 anchored findings, each
  explicitly allowed to report "no findings" rather than manufacture something.
- A cost/finance lens with a strict anchoring rule: it only reports on cost where real
  data exists (usage reports, invoices, a paired tool's proxy stats, or logged
  timestamps), and if none exists, it says so once rather than inventing an ROI figure.
- A project-personas extension point, so you can add domain-specific reviewers (an
  on-call engineer, a specific stakeholder role) without touching the standing lens set.

## Adapting this skill

**The finance lens's anchoring rule is written to be tool-agnostic** — it names
"a paired skill's proxy stats" as one admissible source, using the `critique` skill's
counters block as an example, but doesn't require that skill to be installed. If you use
a different review or logging tool, the lens still works: point it at whatever proxy
metrics your own tooling produces, or leave it to fall back to timestamp-based timing.

**To add a persona,** define it in your project config with a `name` and a `mandate`
(the perspective and its standing questions), following the worked example at the bottom
of `panel.md`. It then competes for a lens slot like any standing lens, under the same
3-finding and anchors-mandatory rules.

**To change the lens set itself**, edit `panel.md` directly — each lens is a self-
contained block of standing questions; adding, removing, or rewording one doesn't affect
the others.

## Files

```
SKILL.md                    LOG/RUN modes, tiers, LITE invocation, output schema
references/panel.md         facilitator protocol + 8 lenses + project-persona extension point
```

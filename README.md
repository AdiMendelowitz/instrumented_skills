# claude-skills

Four Claude skills that share one discipline: log state externally, read it back before
acting, and keep decided separate from suggested — so repeated work on the same target
compounds instead of restarting from zero.

- **[`critique/`](critique/)** — adversarial multi-lens review of a file. Reads its own
  prior run before starting, so a second pass reconciles what changed instead of
  re-discovering what didn't.
- **[`token-aware/`](token-aware/)** — LLM cost reduction for prompts and pipelines.
  Deterministic arithmetic in Python, rate figures dated and source-tagged, a loader that
  refuses stale numbers rather than returning them.
- **[`retrospective/`](retrospective/)** — panel-style retros with a fixed set of
  anchored lenses (no lens may report a finding it can't point to evidence for), plus a
  cost lens that reports no findings rather than inventing an ROI figure when no real
  cost data exists.
- **[`handoff/`](handoff/)** — a structured end-of-session snapshot, schema-based instead
  of prose, so a decision and a suggestion can't collapse into the same sentence a few
  sessions later.

Full writeup of the reasoning behind these: **[link to blog post]**.

## Status of this repo

`critique` and `token-aware` ship complete: full protocols, references, and (for
`token-aware`) a tested cost toolkit — 36/36 tests pass, run them yourself before
trusting the numbers, not instead of running them. `retrospective`'s core protocol and
its panel/lens reference file are both complete. `handoff`'s protocol is a
reconstruction built from a fully worked output example rather than a verbatim
original — read it once before relying on it; see the note at the top of its `SKILL.md`.

None of the four needs authoring from scratch. What every one of them still needs from
you: `token-aware/tools/rates.json` has placeholder rates and an intentionally-expired
date (see its `_comment` field), so fill in real, verified figures before using it for
actual cost figures. Check the ⚠️ / note sections in each skill's README before relying
on it for anything load-bearing.

## Install

Each skill is a self-contained folder. On Claude Code or any surface with a persistent
filesystem, the fastest path is the install script at the repo root — it copies each
selected skill to `~/.claude/skills/`, archives whatever it replaces first, and (for
`token-aware`) runs its test suite as a sanity check afterward:

```bash
git clone <this-repo-url>
cd claude-skills

./install.sh                              # macOS/Linux, installs all four skills
./install.sh critique token-aware         # or just the ones you want
```

```powershell
.\install.ps1                                   # Windows, installs all four skills
.\install.ps1 -Skills critique,token-aware       # or just the ones you want
```

To copy a skill by hand instead — or onto a hosted chat surface with project-level
custom instructions, where you'd upload the folder's contents or paste `SKILL.md` plus
references into your project's instructions — just copy the folder:

```bash
cp -r claude-skills/critique ~/.claude/skills/
```

Or download the folder(s) you want directly from GitHub without cloning the whole repo,
using the "Download" option on an individual folder, or GitHub's zip download for the
full repository.

## How the skills connect

They're independent — none requires another to be installed — but two connections are
worth knowing about:

- `critique`'s log entries carry a `counters` block (calls, bytes, new findings, carried
  findings, whether the prior patch was promoted). `token-aware/tools/cost.py`'s `cpd`
  subcommand reads that block to compute effort-per-finding metrics with no currency
  conversion — useful specifically because not all work is billed per token.
- `retrospective`'s finance lens can use that same `counters` block as one of its
  admissible evidence sources when anchoring a cost-related finding.

Both connections are read-only and optional: `critique` works standalone, and
`token-aware` and `retrospective` fall back gracefully when no counters data exists.

## Customizing for your own setup

Every skill's README has an "Adapting this skill" section covering the parts that are
genuinely environment-specific — where logs live on your surface, how to add a lens or
persona, how to fill in current rates. The mechanism (log, reconcile, don't re-derive) is
meant to transfer directly; the specifics (paths, project names, current pricing) are
not, and are flagged everywhere they appear.

## License

[choose and add a LICENSE file — MIT or Apache-2.0 are common choices for this kind of
tooling]

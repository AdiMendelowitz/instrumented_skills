# instrumented_skills

Five Claude skills that share one discipline: log state externally, read it back before
acting, and keep decided separate from suggested, so repeated work on the same target
compounds instead of restarting from zero.

- **[`critique/`](critique/)**. Adversarial multi-lens review of a file. Reads its own
  prior run before starting, so a second pass reconciles what changed instead of
  re-discovering what didn't.
- **[`token-aware/`](token-aware/)**. LLM cost reduction for prompts and pipelines.
  Deterministic arithmetic in Python, rate figures dated and source-tagged, a loader that
  refuses stale numbers rather than returning them.
- **[`retrospective/`](retrospective/)**. Panel-style retros with a fixed set of
  anchored lenses (no lens may report a finding it can't point to evidence for), plus a
  cost lens that reports no findings rather than inventing an ROI figure when no real
  cost data exists.
- **[`handoff/`](handoff/)**. A structured end-of-session snapshot, schema-based instead
  of prose, so a decision and a suggestion can't collapse into the same sentence a few
  sessions later.
- **[`kb-search/`](kb-search/)**. Ranked BM25 search over the durable artifacts the other
  four write. The shared read-path that lets a run ask whether a root cause fired on any
  other target, not just the one in front of it. Standard library only, no LLM call.

A companion write-up on the reasoning behind these will be linked here once it's published.

## Status of this repo

`critique` and `token-aware` ship complete: full protocols, references, and (for
`token-aware`) a tested cost toolkit (36/36 tests pass). Run them yourself before
trusting the numbers, not instead of running them. `kb-search` ships a standard-library
search toolkit with a passing test suite; run it for the current count, since a number in
prose drifts as tests are added. `retrospective`'s core protocol and its panel/lens
reference file are both complete. `handoff`'s protocol is a reconstruction built from a
fully worked output example rather than a verbatim original. Read it once before relying
on it, and see the note at the top of its `SKILL.md`.

None of the four needs authoring from scratch. What every one of them still needs from
you: `token-aware/tools/rates.json` has placeholder rates and an intentionally-expired
date (see its `_comment` field), so fill in real, verified figures before using it for
actual cost figures. Check the ⚠️ / note sections in each skill's README before relying
on it for anything load-bearing.

## Install

Each skill is a self-contained folder. On Claude Code or any surface with a persistent
filesystem, the fastest path is the install script at the repo root, it copies each
selected skill to `~/.claude/skills/`, archives whatever it replaces first, and (for
`token-aware`) runs its test suite as a sanity check afterward:

```bash
git clone <this-repo-url>
cd instrumented_skills

./install.sh                              # macOS/Linux, installs all five skills
./install.sh critique token-aware         # or just the ones you want
```

```powershell
.\install.ps1                                   # Windows, installs all five skills
.\install.ps1 -Skills critique,token-aware       # or just the ones you want
```

To copy a skill by hand instead, or onto a hosted chat surface with project-level
custom instructions, where you'd upload the folder's contents or paste `SKILL.md` plus
references into your project's instructions, just copy the folder:

```bash
cp -r instrumented_skills/critique ~/.claude/skills/
```

Or download the folder(s) you want directly from GitHub without cloning the whole repo,
using the "Download" option on an individual folder, or GitHub's zip download for the
full repository.

## How the skills connect

Each skill works standalone, but the set is designed to compose. Four of them write
durable artifacts (critique logs, retro journals, handoff snapshots, token-aware cost
logs); `kb-search` is the shared read-path over all of them, and `token-aware` owns the
policy that says when to use it.

- `kb-search` reads what the others write. `critique` reconciles a target against its own
  last log entry; `kb-search` lets a run ask whether the same root cause fired on any
  *other* target. A retro can check whether a long-horizon action was ever done; a handoff
  can search prior snapshots for what a past session settled. It defers one decision,
  grep-first versus escalate, to `token-aware/references/search_policy.md`, which is a hard
  dependency: install `token-aware` alongside it.
- `critique`'s log entries carry a `counters` block (calls, cap, bytes, out_chars, a SEV
  histogram, new findings, carried findings) alongside a top-level `promoted` flag.
  `token-aware/tools/cost.py`'s `cpd` subcommand reads both to compute effort-per-finding
  metrics with no currency conversion, useful specifically because not all work is billed
  per token.
- `retrospective`'s finance lens can use that same `counters` block as one of its
  admissible evidence sources when anchoring a cost-related finding.
- `retrospective` also exposes a LITE invocation path: a review or handoff skill can
  trigger a reduced-scale retro when its own condition fires (a review that closes out a
  project, a handoff that surfaces the same pattern a third time).
- `handoff`'s "Handoff to review" section flags when a review pass is warranted, without
  performing one itself, so a session ending with open SEV1/SEV2-equivalent issues does
  not silently defer them.

Every connection is read-only and, apart from kb-search's policy dependency, optional:
`critique` works standalone, and `token-aware` and `retrospective` fall back gracefully
when no counters data exists.

## Customising for your own setup

Every skill's README has an "Adapting this skill" section covering the parts that are
genuinely environment-specific: where logs live on your surface, how to add a lens or
persona, how to fill in current rates. The mechanism (log, reconcile, don't re-derive) is
meant to transfer directly; the specifics (paths, project names, current pricing) are
not, and are flagged everywhere they appear.

## License

MIT. See [`LICENSE`](LICENSE).

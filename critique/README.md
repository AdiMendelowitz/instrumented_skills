# critique

Adversarial multi-lens review for a document, prompt, or code file. Selects lenses by
what the target is, scales its budget by size, patches severity-1 and severity-2 findings
into a versioned copy, and — the part that makes repeated reviews cheap — reads its own
prior run before starting, so a second pass on the same file reconciles what changed
instead of re-discovering what didn't.

## What it does

1. Reads the file (or files), picks a review tier by size, and selects lenses based on
   what kind of target it is (code, prompt/process doc, architecture doc, ML doc, or a
   set of cross-referencing files).
2. Runs five always-on lenses (purpose/product, evidence-integrity, falsification,
   pre-mortem, red-team) plus whatever the matched bundle adds.
3. Ranks findings by severity and fix cost, patches SEV1/SEV2 into `<name>.v<N+1>.<ext>`
   beside the original, and reports a regression pass on the diff.
4. Logs the run — findings, severities, whether the prior patch was actually promoted —
   so the next run on the same target can reconcile instead of re-deriving.

## Install

Copy `SKILL.md` and the `bundles/` folder to wherever your Claude surface reads skills
from (`~/.claude/skills/critique/` for Claude Code; a project's custom instructions or
skill upload for claude.ai). Both must travel together — `SKILL.md` references the
bundles by relative path and won't select lenses correctly without them.

## Use

Invoke with a target path and, optionally, a purpose: `/critique path/to/file.md "purpose"`.
On a first run against a file with no prior log entry, it behaves like a normal single
review. Run it again on the same target and it reconciles against the last entry instead.

## Adapting this skill

Two things are environment-specific and worth deciding before your first real run:

**Where the log lives (P1).** On a surface with a persistent filesystem and a project
(Claude Code, a checked-out repo), the log writes to
`${CLAUDE_PROJECT_DIR}/.claude/critique-log/<slug>.jsonl` by default — no setup needed.
On a hosted chat surface with no persistent filesystem, the log has to live in memory
instead. Decide once which of your projects get their own memory index (worth it once a
project accumulates enough critique history that cross-session reconciliation matters)
versus a shared general index for everything else.

**The fix-everything preference (P5).** By default, only SEV1 and SEV2 findings get
patched automatically; SEV3 goes to backlog. If you want SEV3 and accepted additions
patched too without saying so on every invocation, that preference needs a home — a
project config file the skill can read (e.g. a `CLAUDE.md` on Claude Code), or a memory
entry on a surface with persistent memory. `SKILL.md` § P5 checks for it in both places;
you only need to actually put it somewhere.

Everything else — the lens definitions, the severity taxonomy, the log schema — works
without edits. If you want a different or additional lens, the `bundles/` files are the
place: each one is a flat list of standing questions per lens, matched to a target
signature in `SKILL.md` § P2.

## Extending the bundle set

To review a target type none of the five bundles cover, add a new bundle file starting
with `# Bundle: <name>` and add a row to the signature table in `SKILL.md` § P2. Keep the
always-on five lenses as the baseline; a new bundle should add lenses, not replace them.

## Files

```
SKILL.md              the protocol
bundles/code.md        lenses for scripts and codebases
bundles/docs.md         lenses for prompts, instructions, process docs
bundles/systems.md      lenses for architecture/design docs, plus a standalone finance section
bundles/ml.md            lenses for ML, modeling, and analytics docs
bundles/multifile.md    lenses for sets of documents that reference each other
evals/                  regression cases for testing changes to this skill (see evals/README.md)
```

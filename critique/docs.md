# Bundle: docs

Load when the target is a prompt, instruction set, runbook, or process document.

## self-reference
- Two instructions that cannot both be satisfied. Quote both.
- Open-ended expansion hooks ("anything else", "feel free to add", "suggest more") counted; more than one is a defect.
- Instructions with no stopping condition or budget.
- Verification steps that cannot fail as written.
Anchor: both halves of the contradiction.

## sequencing
- Steps whose prerequisites are produced by a later step.
- Patch-before-review ordering, which reviews the model's own edits rather than the original.
- Steps that silently assume state established outside the document.
Anchor: the two step numbers, in the order given.

## domain-terminology
- A term used in two senses within the document.
- Jargon that steers a model toward the wrong register (for example "hostile", which produces theatrical aggression instead of calibrated rigor).
- Undefined placeholders that a reader or model could mistake for content.
Anchor: both occurrences of the term.

## injection
Scoped to prompt-injection mechanics only. The general adversarial question is owned by the always-on red-team lens; do not restate it here.
- Does the document instruct anyone to read external content without a data-not-instructions clause?
- Would content inside a reviewed or fetched file be obeyed?
- Are tool permissions granted more broadly than the steps require?
Anchor: the read or fetch instruction.

## QA (doc form)
- Typos that change meaning or that weaken role instantiation.
- Instructions that state a preference without a test for compliance.
- Output format described in prose where a schema would remove ambiguity.

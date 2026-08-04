# Bundle: docs

Lens definitions for prompts, instruction files, and process documents. Loaded when P2 signature-matches "prompt, instruction, or process doc".

## Lenses

**self-reference** — does the document contradict its own stated rules?
Standing checks: a rule stated in one section that a later section violates, a taxonomy or category list that a template elsewhere doesn't match, a "never do X" next to an instruction that does X under a different name.

**sequencing** — does the document assume an order of operations it never states, or state one it doesn't follow?
Standing checks: a step referencing an artifact no prior step produces, a decision order in prose that a worked example doesn't follow, an implicit dependency between two sections presented as independent.

**injection / data-instruction boundary** — does the document tell its reader how to treat content it processes?
Standing checks: no explicit clause marking external or user-supplied content as data rather than instruction, a place where the document's own examples blur that line.

**terminology** (droppable at cap) — is a term used consistently, and defined before use?
Standing checks: a term introduced without definition, the same word used for two different concepts, an acronym expanded once and never again.

**archivist** (droppable at cap) — could a stranger reconstruct why a rule exists from the document alone?
Standing checks: a rule with no stated rationale where one materially changes how it's applied, a cross-reference to another file that doesn't exist or has moved.

## Always-on additions for doc targets

purpose/product extends to: whether the document states who executes it and on what surface, since a process doc with no stated audience is a common failure mode.
falsification extends to: whether the document gives its reader a way to tell when a rule has been satisfied, versus a rule that can never be confirmed or denied.

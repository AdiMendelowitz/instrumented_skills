# Bundle: code

Lens definitions for script, module, and codebase targets. Loaded when P2 signature-matches "script or code file".

## Lenses

**correctness**: does the code do what it claims, on the inputs it will actually see?
Standing checks: off-by-one and boundary conditions, error handling that swallows rather than surfaces, mutable default arguments, state leaking across calls that should be pure, silent truncation on numeric or string operations.

**test coverage**: is the test suite actually exercising the risk?
Standing checks: assertions that check the mock rather than the behaviour, missing edge cases named in the code's own docstrings, a test suite that passes on a broken implementation because it tests the wrong layer, boundary cases stated in comments but never asserted.

**cost** (droppable at cap): token or compute cost of the code path itself, where the target calls an LLM or runs at scale.
Standing checks: unbounded retries, missing caps on generated output, N+1 calls where one batched call would do, a loop that re-derives a value available once at setup.

**integration** (droppable at cap): how this code behaves at its boundaries.
Standing checks: unhandled API error shapes, assumptions about a caller's environment that aren't declared, a public function whose contract isn't stated anywhere.

**terminology** (droppable at cap): naming and vocabulary consistency.
Standing checks: the same concept named two different ways across the file, a name that implies a behaviour the code doesn't have, abbreviations used without being defined once.

## Always-on additions for code targets

evidence-integrity extends to: a comment claiming a behaviour the code doesn't implement, a docstring describing parameters that no longer exist.
red-team extends to: what happens if this function receives adversarial input, what an attacker with read access to logs could infer, which validation is client-side only.

# Bundle: code

Load when the target is a script, module, or source file.

## tech
- Boundary conditions: empty input, single element, maximum size, unicode, negative and zero.
- Silent coercion: implicit type conversion that changes results without raising.
- Mutable default arguments, shared state across calls, aliasing of caller-owned objects.
- Error paths that swallow the exception and continue with a partial result.
Anchor: the exact line implementing the branch.
False positive to avoid: flagging defensive code as dead when the caller is external.

## QA
- Requirements in comments or docstrings that no test can distinguish from their negation.
- Tests asserting the implementation rather than the contract.
- Missing cases for every branch you flagged under tech.
Anchor: the assertion or the missing case, named.

## security
- Untrusted input reaching exec, eval, subprocess, deserialization, SQL, or a path join.
- Secrets in source, in defaults, or in log statements.
- Trust boundary crossings with no validation on the far side.
Anchor: the sink line plus the source line.
Report the reachable path or do not report it.

## integration
- Function signature or return shape that callers elsewhere assume differently.
- Version-pinned behavior that the environment does not guarantee.
- Retry, timeout, and partial-failure handling for every external call.
Anchor: caller and callee both cited.

## cost-runtime
- Work inside a loop that is invariant to the loop.
- Repeated IO or API calls where one batched call is available.
- Data structures with the wrong access pattern for the dominant operation.
- For LLM calls: prompt rebuilt per item where a cached prefix would serve.
Anchor: the loop header and the invariant line.
State the order of magnitude, not a percentage you cannot compute.

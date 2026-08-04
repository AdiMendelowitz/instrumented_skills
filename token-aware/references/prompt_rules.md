# Prompt construction rules | v1.2 | template

For calls you author or review. Model assignment, caching, and cost figures are in `pricing.md`.

## Planning gate

Before writing a prompt for an agentic coding tool: list every file it must read, create, or edit; identify blocking unknowns that must be resolved before any code is written; assign a pinned model string to every LLM call the prompt will produce; reference your project's existing code-quality or review-gate rules rather than restating them.

## Rules

Token figures quoted in these rules are working defaults, not measurements from your pipeline. Where a rule is load-bearing for a decision, measure it on your own calls before relying on the number.

**No role-play preamble on extraction or classification calls.** A long persona costs tokens with no measurable gain on structured output. Reserve persona for synthesis and open-ended calls where it shapes depth.

```
# Before: "You are a senior quantitative analyst with 20 years at Goldman Sachs..."
# After:  "You are a quantitative analyst."
```

**Never repeat content across system prompt and user message.** Keep it in the system prompt, where it caches. Remove it from the user message entirely.

**Send derived values, not raw data.** If you already compute six indicators from thirty raw rows, send the six computed values, not the thirty rows. Compute first, send the result.

**One schema description, one location.** The system prompt owns it.

**One example per extraction call.** Examples cost linearly and rarely improve structured output. Exception: more than five output classes with genuinely ambiguous boundaries, where you use the minimum that removes the ambiguity.

**JSON-only suffix on every extraction call that does not use tool-based schemas**, replacing all verbose format instructions (calls using `tool_use` skip it; see below):
```
Return JSON only. No prose. No markdown fences.
```

**`max_tokens` at the minimum plausible.** Unbounded output is unbounded cost. Log a warning when actual output exceeds 90% of the cap, since that means silent truncation.

**`temperature=0` on deterministic extraction.** Higher temperature raises format-error rate, and every retry pays the full prompt again.

**Prefer `tool_use` for structured output on any call where JSON parse failures occur.** Schema enforcement at the API level removes the retry class entirely. This supersedes prompt-level format instructions rather than supplementing them, including the JSON-only suffix above. It applies only where every provider behind the call supports tool schemas: in a multi-provider router, portability wins and the JSON-only suffix stays.

**Reduce output tokens before moving model tiers.** Output typically costs a multiple of input (current ratio in `pricing.md`), so a schema returning three fields instead of eight beats a downgrade in most pipelines. Cap free-text fields explicitly: `"reasoning": string, max 20 words`. Request only fields you parse; the model will not generate what the schema omits.

**Short JSON keys are a false economy in most cases.** Renaming `action` to `a` saves a handful of output tokens and removes the semantic cue that guides structured generation, which raises format-error and retry rates. It is also incompatible with `tool_use` schema enforcement and with strict schema validation. Use it only on a very high-volume call where you have measured both the token saving and the error rate, and never on a call using tool-based schemas.

**Centralise prompt construction.** One module, never inline in agent files, so token estimation, truncation, and suffix enforcement have a single point of control.

## Batching versus caching

Putting N items in one call pays the instruction tokens once instead of N times. It also, in order of importance: raises output tokens on a single call and risks hitting `max_tokens` with silent truncation; couples failures, so one malformed item can fail the batch; and competes with caching, because N calls sharing a cached prefix pay the cache-read multiplier in `pricing.md` on that prefix after the first.

Decide by measurement, not by assumption. Where the workload is scheduled, the Batch API gives the discount stated in `pricing.md` with none of these trade-offs and should be evaluated first.

---
name: token-aware
description: Reduce LLM cost in prompts, pipelines, and code that calls an LLM, and author cost-aware prompts for other Claude surfaces to run. Use for token or cost audits, model routing, prompt caching, batching, replacing an LLM call with deterministic code, or writing an instruction file that will execute elsewhere. Not for general code or performance optimisation.
---

# Token-Aware Prompting and Code Generation | v2.1 | 2026-07-30

## Core principle

An LLM call is justified only where the output is irreducibly qualitative prose: judgement, synthesis, narrative that a Python function cannot produce at equivalent quality. Everything else is Python.

Applies in two directions: prompts written for Claude Code, and Python that Claude Code produces.

## References, load on demand

- `references/pricing.md` — how to get current rates, caching math, batch API, what not to hardcode. **Read before quoting any cost figure or ratio.**
- `references/prompt_rules.md` — prompt construction rules for calls you author
- `references/python_replacements.md` — REPLACE patterns with worked code
- `references/module_layout.md` — prompt builders, token estimation, module structure
- `references/audit_workflow.md` — auditing an existing codebase, report template
- `references/search_policy.md` — canonical layer order for retrieval (grep, then kb-search, then a code-graph tool); `kb-search` treats this file as a hard dependency, so keep it here even as this skill's own content evolves

The Python-first rule and the code review gate live in the project CLAUDE.md for any project that has one. This skill does not restate them; it supplies the reasoning behind them and the audit procedure that enforces them.

## Precedence

For which retrieval tool to reach for (grep, then kb-search, then a code-graph tool), `references/search_policy.md` is canonical; follow its layer order rather than restating it here.

A project CLAUDE.md that sets model assignments, thresholds, or a review gate outranks this skill for that project; this skill supplies the reasoning and the audit procedure, not the project's settings. Where both speak, follow the project file and name the difference in one line. For task ownership: `ds-ml-technical-mode` owns implementation, `critique` owns adversarial file review, this skill owns cost.

## Two roles, and they use different environments

**Auditing here.** The code is reachable from the current session. What is reachable differs by surface; see `audit_workflow.md` § Environments.

**Authoring for elsewhere.** Writing a prompt, spec, or markdown file that another surface will execute. The target environment is the one that will run it, not the one you are in. A prompt written on claude.ai for Claude Code says `graphify update .` and gives the PowerShell sweep, even though neither can run where it was written. State the target environment in the first line of anything you author, so the reader and the executing agent agree on what is available.

Never emit an instruction the target cannot run, and never withhold one because the current surface cannot run it. Those are different mistakes and the second is the easier one to make.

## Taxonomy

Assign every LLM call exactly one primary label. CACHE and DOWNGRADE combine.

```
REPLACE   deterministic task; Python produces equivalent output. Requires an
          agreement measurement before it ships. See the accuracy gate below.
DOWNGRADE needs judgement but not the largest model. Move to the cheapest model
          that reliably holds the output format.
CACHE     stable prefix above the model's minimum cacheable length, re-read
          inside the TTL. Verify it actually cached; silent no-cache is the
          normal failure.
TRIM      prompt contains removable tokens. Cut without changing the task.
KEEP      genuinely requires judgement and the prompt is already minimal.
          Written justification required, inline and in the report.
```

See § Decision order below for the fuller walk-through of the same five categories in the order they're evaluated; this block is the quick-reference form.

## Decision order

1. **BATCH** if the work is scheduled or non-interactive. Halves input and output, no quality risk, no prompt change. It is a different endpoint with submit-and-poll semantics, so converting a synchronous pipeline is a structural change: largest saving, not the smallest effort.
2. **REPLACE** where the task is deterministic and the accuracy gate passes. Eliminates cost entirely.
3. **DOWNGRADE** to the cheapest model holding the format. The saving is smaller than it used to be: verify the current ratio from `pricing.md` rather than assuming a large multiple.
4. **CACHE** where the prefix is stable, above the model's minimum, and re-read inside the TTL.
5. **TRIM** last. Incremental.

## The accuracy gate on REPLACE

Cost is one axis. A REPLACE that changes behaviour is a regression sold as a saving, and the audit workflow has no other place to catch it.

Before any REPLACE ships:

- **Deterministic substitutions** (arithmetic, formatting, threshold comparison against a named constant, field extraction) need only the unit tests in `audit_workflow.md` § Step 5. The output is provably identical.
- **Judgement substitutions** (intent classification, routing, labelling, trend direction, anything where the LLM was making a call a human could disagree with) need a measured agreement rate against the LLM on a held-out sample of real production inputs. State the sample size, the agreement rate, and where the disagreements fall. Ship only if the disagreements are acceptable, and say why.
- A keyword `frozenset` is not equivalent to intent classification. It is a cheaper approximation whose error rate you have to know before you accept it.
- Record the measurement next to the token saving. A REPLACE with a saving and no agreement number is not audited, it is asserted.

## The fuzzy-intent boundary

Keyword matching in Python handles known explicit terms. Use an LLM for intent classification only when the query is open-ended and the possible intents cannot be enumerated in advance. If you can write a keyword list that provably covers production cases, it is Python, and "provably" means measured per the gate above.

## Protected calls

Always LLM-appropriate. Never REPLACE or DOWNGRADE:

- Synthesis across conflicting signals into a unified directional narrative
- Sceptic or challenger analysis requiring genuine counter-reasoning
- Open-ended qualitative output read by a human rather than parsed as data
- Any call whose output format cannot be specified as a complete schema in advance

Route protected calls to the mid tier, not the top tier. The flagship model is for one-time research where reasoning depth justifies the cost, not for pipeline calls.

## Prompt versioning

Prompts are code. Templates in `prompts/` with version suffixes, changes committed alone with before and after token counts in the message, previous version retained until the new one is validated in production. A trim that degrades quality needs a rollback path that exists.

## What this skill does not do

It does not review code for correctness, security, or maintainability. That's a code-review or `critique`-style skill's job, and this skill should name the difference rather than drift into it. It does not decide *whether* to make an LLM call at all, only how to make the calls that exist more cheaply. And it does not invent a dollar figure for work that isn't actually billed per token; see `references/pricing.md`'s framing on subscription versus metered work if that distinction applies to your usage.

---
name: token-aware
description: Reduce LLM cost in prompts, pipelines, and code that calls an LLM, and author cost-aware prompts for other Claude surfaces to run. Use for token or cost audits, model routing, prompt caching, batching, replacing an LLM call with deterministic code, or writing an instruction file that will execute elsewhere. Not for general code or performance optimization.
---

<!--
TODO before publishing: this file is a placeholder. The working SKILL.md for this skill
(v2.3, ~100 lines) was not present in the project files used to generate this repo scaffold
— only its three reference files (references/pricing.md, references/audit_workflow.md,
references/prompt_rules.md) and its tools/ folder were available, and those are already
in place below. Copy your actual SKILL.md in here before this repo goes public; the
reference files already point back to it (e.g. "canonical clause in SKILL.md § Two roles",
"decision order in SKILL.md") so the skill will not select correctly without it.

From prior session history, this file defines at minimum:
  - § Two roles: the canonical data-not-instructions clause that references/audit_workflow.md
    and references/pricing.md point back to.
  - § Precedence: a project config (e.g. CLAUDE.md) outranks this skill's own model/threshold
    defaults for that project; this skill supplies reasoning and audit procedure, not settings.
  - A decision order for optimizations: BATCH, then REPLACE (with an accuracy/agreement
    gate), then DOWNGRADE, then CACHE, then TRIM — see references/audit_workflow.md § Step 3
    for the same order restated on the audit side.
  - A taxonomy of call types this skill applies to, and which ones it explicitly excludes.

Generalize before publishing: remove any project-specific model pins, thresholds, or
call-site examples and replace with placeholders, per README.md § Adapting this skill.
-->

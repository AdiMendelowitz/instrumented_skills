# Module layout and token estimation | v1.2 | 2026-08-03

## Structure

```
utils/
├── python_replacements.py   REPLACE functions. Pure, no side effects, no network.
├── prompt_builders.py       All prompt construction. No API calls.
└── llm_client.py            Every client.messages.create() call. Nowhere else.
```

`python_replacements.py` module docstring, verbatim:

```python
"""
Pure Python replacements for LLM calls identified during the token optimization audit.

Every function documents:
  - which call it replaces (file + function name)
  - why Python is sufficient (deterministic / numeric / structural)
  - estimated tokens saved per call (input + output)
  - for judgment substitutions: measured agreement rate against the removed call,
    the sample size, and where the disagreements fall

Interface contract: output is drop-in compatible with what the replaced call returned.
Callers require zero changes to parsing logic.

No API calls. No network. No side effects. All functions pure.
"""
```

## Token estimation

A character-based estimate is a budgeting aid, never a billing figure. Two things make it unsafe if the direction is not understood.

Dividing character count by a chars-per-token constant produces a **smaller** number as the constant grows. To over-estimate, and therefore over-budget, the constant must be **below** the true average. English prose runs near 3.5 characters per token and code nearer 2.5, so a constant of 4 under-estimates prose by roughly 12% and code by far more. The previous version of this skill used 4 and described it as a conservative over-estimate, which was backwards.

Claude 4.7 and later tokenize roughly 30% more densely than earlier models for the same text, so any constant calibrated on an older model under-reports on a newer one.

```python
"""utils/prompt_builders.py: centralized prompt construction."""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

# Two constants, because budgeting and truncation have opposite error costs.
# Budgeting wants to over-estimate tokens (warn early, never under-reserve), so it
# divides by a value below the true average. Truncation over-estimating by 40% throws
# away 40% of content it could have kept, so it uses the realistic value for the
# content type. Prose runs near 3.5 chars/token, code nearer 2.5.
# Recalibrate against count_tokens per content type and after any model change.
CHARS_PER_TOKEN_PROSE: float = 3.5
CHARS_PER_TOKEN_CODE: float = 2.5
BUDGET_SAFETY: float = 0.8          # shrinks chars/token, so token estimates run high
TOKEN_WARN_THRESHOLD: int = 2_000
JSON_ONLY_SUFFIX: str = "\n\nReturn JSON only. No prose. No markdown fences."


def estimate_tokens(text: str, code: bool = False) -> int:
    """Deliberate over-estimate, for budgeting and warnings only. Never for billing."""
    base = CHARS_PER_TOKEN_CODE if code else CHARS_PER_TOKEN_PROSE
    return int(len(text) / (base * BUDGET_SAFETY))


def truncate_to_tokens(text: str, max_tokens: int, code: bool = False) -> str:
    """
    Truncate to approximately max_tokens, ending on a whitespace boundary so the
    result reads cleanly and no word is cut mid-way. Python 3 slices by code point,
    so character integrity is not at risk; readability is the only reason for the walk.

    Uses the realistic chars/token for the content type, not the budgeting value.
    Over-estimating here discards content unnecessarily, which is a real loss, while
    a slight under-estimate only risks the cap that max_tokens already guards.
    Where count_tokens is available, prefer it over this estimate for truncation.
    """
    base = CHARS_PER_TOKEN_CODE if code else CHARS_PER_TOKEN_PROSE
    max_chars = int(max_tokens * base)
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    boundary = truncated.rfind(" ")
    if boundary > max_chars // 2:
        truncated = truncated[:boundary]
    return truncated + "\n[TRUNCATED: context exceeded token budget]"


def build_extraction_prompt(system: str, user: str) -> tuple[str, str]:
    """Append the JSON-only suffix and warn if the estimated total is large.

    Prompt-based extraction only: calls using tool_use schemas skip this builder
    and its suffix entirely (prompt_rules.md, tool_use rule).
    """
    user_with_suffix = user + JSON_ONLY_SUFFIX
    total = estimate_tokens(system) + estimate_tokens(user_with_suffix)  # over-estimates by design
    if total > TOKEN_WARN_THRESHOLD:
        logger.warning("Prompt estimated at %d tokens; consider trimming.", total)
    return system, user_with_suffix
```

## Validate estimates against actuals

```python
counted = client.messages.count_tokens(
    model=MODEL,
    system=system_prompt,
    messages=[{"role": "user", "content": user_message}],
)
# Compare against estimate_tokens(system_prompt) + estimate_tokens(user_message).
# The estimate should exceed the actual. If it is lower, CHARS_PER_TOKEN is too
# high for this content type and must be reduced. Recalibrate per content type
# and after any model-generation change.
```

Run this before deploying an optimized prompt, and on the top five most expensive calls during any audit.

`count_tokens` needs an authenticated client, so it is available in Claude Code and in any environment where the project's own client is already configured. It is not available in a plain chat session, and an API key is never pasted into one. Where it cannot run, report the estimate as an estimate and note that it was not validated.
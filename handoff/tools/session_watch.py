"""Session-length watch: surface a fact that makes /handoff timing decidable.

WHY A HOOK AND NOT A CLAUDE.md RULE
-----------------------------------
A standing instruction like "tell me when the session is getting long" cannot work
reliably, because the assistant has no turn counter. It sees a context window, not a
count, and its sense of "how long has this been" is exactly the faculty that degrades
as the session grows. Asking the degrading component to self-report degradation is the
failure mode, not the fix.

This hook counts turns deterministically and states the count as a fact. What to *do*
about it lives in CLAUDE.md, matching the split the hooks reference recommends: dynamic
environment state comes from a hook, static instructions come from CLAUDE.md.

WHY UserPromptSubmit AND NOT Stop
---------------------------------
A Stop hook fires when the session is already ending, too late to suggest wrapping up.
UserPromptSubmit fires before each prompt is processed, so the signal lands while there
is still session left to act on.

FOUR CONSTRAINTS FROM THE HOOKS REFERENCE, ALL LOAD-BEARING HERE
----------------------------------------------------------------
1. Plain-text stdout, not JSON. For UserPromptSubmit, stdout is added to context
   directly. A known Claude Code issue (anthropics/claude-code#17550) surfaces a
   "UserPromptSubmit hook error" to the user when this event returns
   hookSpecificOutput JSON on the first prompt of a session; plain text does not
   trigger it. Plain text is also officially supported for this event, so the JSON
   form buys nothing here.
2. Factual phrasing, not imperative. The reference warns that text framed as
   out-of-band system commands can trigger prompt-injection defenses, causing the
   assistant to surface the text to the user instead of acting on it. Every string
   this module emits is a statement of fact for that reason.
3. A 30-second timeout, and the hook blocks model processing while it runs. The
   transcript is therefore never fully JSON-parsed: lines are prefiltered by substring
   first, and the hook exits before reading anything at all once its last threshold
   has fired.
4. The transcript lags the live conversation, so the count is a floor, not an exact
   figure. Every message says "at least".

Registration and CLAUDE.md text: see CLAUDE.md-snippet.md beside this file.

Requires Python 3.10+, standard library only. The floor is real rather than nominal:
annotations here use PEP 604 unions evaluated at runtime. This matters more than usual
for a hook, because it runs under whatever interpreter settings.json names, which is
often a system Python rather than a project venv.

Environment overrides:
    HANDOFF_WARN_TURNS   first threshold (default 25)
    HANDOFF_URGE_TURNS   second threshold (default 35)
    HANDOFF_WATCH=0      disable without unregistering
    HANDOFF_WATCH_STATE  override the marker directory
"""

import json
import os
import sys
import time
from pathlib import Path

DEFAULT_WARN_TURNS = 25
DEFAULT_URGE_TURNS = 35

MARKER_TTL_SECONDS = 30 * 24 * 60 * 60  # prune markers after 30 days
PRUNE_PROBABILITY_DIVISOR = 20  # prune on roughly 1 run in 20, not every run

# Cheap prefilter: a transcript line cannot be a user turn without this substring, and
# assistant lines (the bulk of a transcript, and the largest) are skipped without ever
# reaching json.loads. Both spacings appear across Claude Code versions.
_USER_HINTS = ('"type":"user"', '"type": "user"')


class Level:
    WARN = "warn"
    URGE = "urge"


def _int_env(name: str, default: int) -> int:
    """Read a positive int from the environment, falling back on anything unparseable.

    A malformed override must never break the user's ability to submit a prompt.
    """
    try:
        value = int(os.environ.get(name, ""))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def thresholds() -> tuple[int, int]:
    """Warn and urge thresholds, with urge forced above warn.

    A configuration where urge <= warn would make the second, stronger signal
    unreachable, so it is corrected rather than honored.
    """
    warn = _int_env("HANDOFF_WARN_TURNS", DEFAULT_WARN_TURNS)
    urge = _int_env("HANDOFF_URGE_TURNS", DEFAULT_URGE_TURNS)
    if urge <= warn:
        urge = warn + 10
    return warn, urge


def count_user_turns(transcript_path: Path) -> int:
    """Count genuine user turns in a Claude Code transcript (JSONL, one event per line).

    Counts only real user messages. Tool results are also recorded with type "user" in
    Claude Code transcripts, and counting them would inflate the number several-fold on
    any tool-heavy session, firing the nudge far too early exactly where a false alarm
    is most disruptive. Meta and sidechain (subagent) events are excluded for the same
    reason.

    The returned count is a floor: the hooks reference notes the transcript file is
    written asynchronously and may lag the in-memory conversation.
    """
    turns = 0
    try:
        with transcript_path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if not any(hint in line for hint in _USER_HINTS):
                    continue  # prefilter: no JSON parsing for the ~90% that can't match
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") != "user":
                    continue
                if event.get("isMeta") or event.get("isSidechain"):
                    continue
                content = (event.get("message") or {}).get("content")
                if isinstance(content, str):
                    if content.strip():
                        turns += 1
                elif isinstance(content, list):
                    # A real user turn carries a text block. A tool result carries
                    # tool_result blocks and no text.
                    if any(
                        isinstance(block, dict)
                        and block.get("type") == "text"
                        and str(block.get("text", "")).strip()
                        for block in content
                    ):
                        turns += 1
    except (OSError, ValueError):
        return 0
    return turns


def state_dir() -> Path:
    """Where firing markers live.

    Deliberately not the transcript's own directory: that belongs to Claude Code, and
    writing marker files into it risks colliding with its layout.
    """
    override = os.environ.get("HANDOFF_WATCH_STATE")
    if override:
        return Path(override)
    return Path.home() / ".claude" / "handoff-watch"


def already_fired(base: Path, session_id: str, level: str) -> bool:
    return (base / f"{session_id}.{level}").exists()


def mark_fired(base: Path, session_id: str, level: str) -> None:
    """Record that a level fired, so it does not repeat on every subsequent prompt.

    Failure to persist is non-fatal: a repeated nudge is a far smaller problem than a
    hook that raises and interferes with prompt submission.
    """
    try:
        base.mkdir(parents=True, exist_ok=True)
        (base / f"{session_id}.{level}").touch()
    except OSError:
        pass


def prune_markers(base: Path, now: float | None = None) -> int:
    """Delete markers past their TTL so the directory cannot grow without bound.

    One marker per session per level is tiny, but a hook that never cleans up is a slow
    leak in a directory the user never looks at.
    """
    now = now if now is not None else time.time()
    removed = 0
    try:
        for marker in base.glob("*.*"):
            try:
                if now - marker.stat().st_mtime > MARKER_TTL_SECONDS:
                    marker.unlink()
                    removed += 1
            except OSError:
                continue
    except OSError:
        return removed
    return removed


def build_message(turns: int, level: str) -> str:
    """The text added to context. Factual statements only.

    The hooks reference warns that imperative, out-of-band-command phrasing can trip
    prompt-injection defenses and get surfaced to the user rather than acted on. These
    strings therefore describe state; CLAUDE.md holds the corresponding instruction.
    """
    noun = "user turn" if turns == 1 else "user turns"
    if level == Level.URGE:
        return (
            f"Session state: this conversation has reached at least {turns} {noun}. "
            f"At this length, details established early in the session are materially "
            f"less reliable than recent ones, and a state snapshot written now will "
            f"capture more than one written later. The /handoff skill writes such a "
            f"snapshot for resuming in a fresh session."
        )
    return (
        f"Session state: this conversation has reached at least {turns} {noun}, "
        f"approaching the length where early-session details become less reliable. The "
        f"/handoff skill writes a state snapshot for continuing in a fresh session."
    )


def main() -> int:
    if os.environ.get("HANDOFF_WATCH") == "0":
        return 0

    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
        return 0  # not invoked as a hook, or malformed input: stay silent
    if not isinstance(payload, dict):
        return 0

    transcript_path = payload.get("transcript_path")
    if not transcript_path:
        return 0
    session_id = str(payload.get("session_id") or "unknown").replace("/", "_").replace("\\", "_")

    base = state_dir()
    warn_at, urge_at = thresholds()

    # Exit before touching the transcript once the last threshold has fired. This is
    # the common case for the whole back half of a long session, and it is what keeps
    # a per-prompt blocking hook off the critical path.
    if already_fired(base, session_id, Level.URGE):
        return 0

    turns = count_user_turns(Path(transcript_path))
    if turns < warn_at:
        return 0

    level = Level.URGE if turns >= urge_at else Level.WARN
    if already_fired(base, session_id, level):
        return 0
    mark_fired(base, session_id, level)

    # Occasional, not every run: pruning is housekeeping and must not add latency to
    # the blocking path more often than it needs to.
    if turns % PRUNE_PROBABILITY_DIVISOR == 0:
        prune_markers(base)

    # Plain text, not JSON: see the module docstring, constraint 1.
    print(build_message(turns, level))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except BaseException:
        # A hook that raises could interfere with prompt submission. Fail open, always.
        raise SystemExit(0)

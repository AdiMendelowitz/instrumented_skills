"""Deterministic checks for handoff documents.

The handoff protocol makes three claims that were previously self-reported by whichever
model wrote the snapshot, rather than verified: that the labeled-line format saves 30-40%
of tokens against prose ("unmeasured"), that STATE line/byte counts are computed rather
than estimated, and that a long session's UNVERIFIED section actually gets the required
context-degradation line. This module checks all three deterministically, the same
principle token-aware applies to cost arithmetic: a claim a protocol makes about numbers
should be checked in code, not trusted in prose.

Subcommands: lint, state-check, compare.
Python 3.10+, standard library only.
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

SECTION_CAPS = {
    "STATE": 8,
    "DECIDED": 10,
    "PROPOSED": 6,
    "REJECTED": 5,
    "OPEN": 5,
    "UNVERIFIED": 5,
    "PATTERN": 3,
    "FIRST": 1,
}
SECTION_ORDER = list(SECTION_CAPS)

HEADER_RE = re.compile(
    r"^HANDOFF v(?P<version>\S+) \| (?P<date>[^|]+) \| supersedes: (?P<supersedes>[^|]+) "
    r"\| session-length: (?P<length>short|long)\s*$"
)
OBJ_RE = re.compile(r"^OBJ: (?P<obj>.+)$")

# Path-shaped STATE rows: <path> | v<x> | <n>L <n>B | <purpose>
STATE_PATH_ROW_RE = re.compile(
    r"^(?P<path>[^|]+?)\s*\|\s*v(?P<version>\S+)\s*\|\s*(?P<lines>\d+)L\s+(?P<bytes>\d+)B\s*\|"
)

CHARS_PER_TOKEN = 3.5  # same constant family as token-aware, for a comparable estimate


@dataclass
class ParsedHandoff:
    header: str | None
    header_fields: dict | None
    obj: str | None
    sections: dict[str, list[str]] = field(default_factory=dict)
    raw: str = ""


def parse_handoff(text: str) -> ParsedHandoff:
    """Split a handoff document into header, OBJ line, and labeled sections.

    Section bodies are the indented lines following a flush-left section label (STATE,
    DECIDED, ...) up to the next label or end of document.

    Indentation is the discriminator, not the first word. The format puts labels
    flush-left and indents their content, so a content line that happens to begin with
    a section word ("PATTERN detection is unreliable" inside OPEN) stays content. Testing
    the first token alone would silently start a new section there and mis-attribute
    every line that followed.
    """
    lines = text.splitlines()
    header = None
    header_fields = None
    obj = None
    sections: dict[str, list[str]] = {name: [] for name in SECTION_ORDER}
    current: str | None = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        indented = raw_line[:1].isspace()
        if not indented and line.startswith("HANDOFF v"):
            header = line
            m = HEADER_RE.match(line)
            header_fields = m.groupdict() if m else None
            continue
        m = OBJ_RE.match(line) if not indented else None
        if m:
            obj = m.group("obj")
            continue
        # A section label is flush-left and starts with a known section name, alone on
        # the line or followed by the "<=N lines, ..." spec comment from the template.
        first_token = line.split()[0]
        if not indented and first_token in SECTION_CAPS:
            current = first_token
            continue
        if current:
            sections[current].append(line)

    return ParsedHandoff(header=header, header_fields=header_fields, obj=obj,
                          sections=sections, raw=text)


def lint(parsed: ParsedHandoff) -> list[str]:
    """Structural violations: caps, header shape, and rules the protocol states but
    doesn't otherwise enforce."""
    violations = []

    if not parsed.header:
        violations.append("no HANDOFF header line found")
    elif not parsed.header_fields:
        violations.append(
            f"header line present but doesn't match the expected shape: {parsed.header!r}"
        )

    if not parsed.obj:
        violations.append("no OBJ line found")

    for name, cap in SECTION_CAPS.items():
        n = len(parsed.sections.get(name, []))
        if n > cap:
            violations.append(f"{name} has {n} line(s), cap is {cap}")

    if len(parsed.sections.get("FIRST", [])) == 0:
        violations.append("FIRST is empty; the protocol requires exactly one executable action")
    elif len(parsed.sections.get("FIRST", [])) > 1:
        violations.append("FIRST has more than one line; it must be singular")

    if parsed.header_fields and parsed.header_fields.get("length") == "long":
        unverified_text = " ".join(parsed.sections.get("UNVERIFIED", [])).lower()
        if "context degradation" not in unverified_text and "degrad" not in unverified_text:
            violations.append(
                "session-length is 'long' but UNVERIFIED has no line flagging context "
                "degradation, which the protocol requires on long sessions"
            )

    return violations


def _resolve_state_path(raw: str, base_dir: Path) -> Path:
    """Resolve a STATE row's path the way a reader would read it.

    Three forms appear in real handoffs and all three must work, because a checker that
    false-alarms on the protocol's own examples is worse than no checker: a home-relative
    path ("~/.claude/skills/..."), an absolute path, and a project-relative path. Only
    the last is joined onto base_dir.
    """
    raw = raw.strip()
    if raw.startswith("~"):
        return Path(raw).expanduser()
    p = Path(raw)
    if p.is_absolute():
        return p
    return base_dir / p


def state_check(parsed: ParsedHandoff, base_dir: Path) -> list[str]:
    """Recompute line/byte counts for path-shaped STATE rows and flag drift.

    Only rows matching the '<path> | v<x> | <n>L <n>B | ...' shape are checked; rows
    for installs or running processes (the other two STATE categories) are skipped,
    since there's nothing on disk to recompute them against.
    """
    findings = []
    for row in parsed.sections.get("STATE", []):
        m = STATE_PATH_ROW_RE.match(row)
        if not m:
            continue  # not a path row (install or process row): nothing to verify
        raw = m.group("path").strip()
        path = _resolve_state_path(raw, base_dir)
        claimed_lines, claimed_bytes = int(m.group("lines")), int(m.group("bytes"))
        if not path.exists():
            findings.append(f"{raw}: claimed {claimed_lines}L {claimed_bytes}B, "
                             f"but no file at {path}")
            continue
        data = path.read_bytes()
        actual_bytes = len(data)
        actual_lines = data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)
        if actual_lines != claimed_lines or actual_bytes != claimed_bytes:
            findings.append(
                f"{raw}: snapshot claims {claimed_lines}L {claimed_bytes}B, "
                f"actual is {actual_lines}L {actual_bytes}B, file changed since the "
                f"snapshot was written, or the count was estimated rather than computed"
            )
    return findings


def estimate_tokens(text: str) -> int:
    """Same estimation family as token-aware's tools/cost.py, for a comparable figure."""
    return int(len(text) / CHARS_PER_TOKEN)


def compare_savings(handoff_text: str, prose_text: str) -> dict:
    """Turn the 'unmeasured' 30-40% claim into an actual figure against a paired prose
    document covering the same content.

    The percentage is independent of CHARS_PER_TOKEN: the constant appears in both
    numerator and denominator and cancels. Changing it moves the two absolute token
    figures and leaves saved_pct identical. The figure's real dependency is that the
    prose file genuinely covers the same content, which no code can check.
    """
    h_tokens = estimate_tokens(handoff_text)
    p_tokens = estimate_tokens(prose_text)
    if p_tokens == 0:
        raise ValueError("prose comparison text is empty; nothing to compare against")
    saved_pct = (p_tokens - h_tokens) / p_tokens * 100
    return {
        "handoff_tokens_estimated": h_tokens,
        "prose_tokens_estimated": p_tokens,
        "saved_pct": saved_pct,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("handoff", help="path to a handoff document")
    ap.add_argument("--lint", action="store_true", help="check caps and structural rules")
    ap.add_argument("--state-check", action="store_true",
                     help="recompute STATE line/byte counts against files on disk")
    ap.add_argument("--base-dir", default=".", help="base directory STATE paths are relative to")
    ap.add_argument("--compare", metavar="PROSE_FILE",
                     help="estimate token savings against a paired prose-equivalent file")
    a = ap.parse_args(argv)

    text = Path(a.handoff).read_text(encoding="utf-8")
    parsed = parse_handoff(text)

    # Default to lint when no flag is given, so a bare invocation still does something useful.
    ran_anything = False
    exit_code = 0

    if a.lint or not (a.state_check or a.compare):
        ran_anything = True
        violations = lint(parsed)
        if violations:
            print(f"{len(violations)} lint violation(s):")
            for v in violations:
                print(f"  {v}")
            exit_code = 1
        else:
            print("lint: clean")

    if a.state_check:
        ran_anything = True
        findings = state_check(parsed, Path(a.base_dir))
        if findings:
            print(f"{len(findings)} STATE drift finding(s):")
            for f in findings:
                print(f"  {f}")
            exit_code = 1
        else:
            print("state-check: all path-shaped STATE rows match files on disk")

    if a.compare:
        ran_anything = True
        prose_text = Path(a.compare).read_text(encoding="utf-8")
        result = compare_savings(text, prose_text)
        print(f"handoff: ~{result['handoff_tokens_estimated']} tokens (estimated)")
        print(f"prose:   ~{result['prose_tokens_estimated']} tokens (estimated)")
        print(f"saved:   {result['saved_pct']:.1f}% (estimate-based, not a real tokenizer count)")

    return exit_code if ran_anything else 1


if __name__ == "__main__":
    raise SystemExit(main())

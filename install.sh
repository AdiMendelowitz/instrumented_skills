#!/usr/bin/env bash
# claude-skills install script (macOS / Linux)
# Run from the root of this repo. Copies each selected skill folder to
# ~/.claude/skills/<name>, archiving whatever it replaces first.
#
# Usage:
#   ./install.sh                              # installs all four skills
#   ./install.sh critique token-aware         # installs only the ones named

set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
STAMP="$(date +%Y%m%d-%H%M)"

if [ "$#" -gt 0 ]; then
    SKILLS=("$@")
else
    SKILLS=(critique token-aware retrospective handoff)
fi

echo "Preflight:"
missing=()
for s in "${SKILLS[@]}"; do
    if [ ! -f "$SOURCE_DIR/$s/SKILL.md" ]; then
        missing+=("$s")
    fi
done
if [ "${#missing[@]}" -gt 0 ]; then
    echo "  Missing SKILL.md for: ${missing[*]}" >&2
    echo "  Nothing was copied. Check the skill names and that this script is at the repo root." >&2
    exit 1
fi
echo "  all requested skill folders present: ${SKILLS[*]}"

mkdir -p "$DEST_DIR"
echo ""
echo "Installing to $DEST_DIR :"
for s in "${SKILLS[@]}"; do
    from="$SOURCE_DIR/$s"
    to="$DEST_DIR/$s"
    if [ -d "$to" ]; then
        cp -R "$to" "$to.bak-$STAMP"
        echo "  archived existing $s -> $s.bak-$STAMP"
    fi
    cp -R "$from" "$to"
    echo "  installed $s"
done

echo ""
echo "Done. Read each skill's README.md for setup steps that can't be scripted"
echo "(filling in token-aware/tools/rates.json, authoring the placeholder SKILL.md"
echo "files flagged in token-aware and retrospective, reviewing handoff's"
echo "reconstructed SKILL.md)."

if printf '%s\n' "${SKILLS[@]}" | grep -qx "token-aware"; then
    echo ""
    echo "Running token-aware's test suite as a sanity check:"
    if command -v python3 >/dev/null 2>&1; then
        (cd "$DEST_DIR/token-aware/tools" && python3 -m pytest -q 2>&1 | tail -5)
    else
        echo "  SKIPPED: python3 not on PATH. Run 'python3 -m pytest -q' in token-aware/tools yourself."
    fi
fi

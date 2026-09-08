#!/usr/bin/env bash
# instrumented_skills install script (macOS / Linux)
# Run from the root of this repo. Copies each selected skill folder to
# ~/.claude/skills/<name>, archiving whatever it replaces first.
#
# Usage:
#   ./install.sh                              # installs all five skills
#   ./install.sh critique token-aware         # installs only the ones named

set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
STAMP="$(date +%Y%m%d-%H%M)"

if [ "$#" -gt 0 ]; then
    SKILLS=("$@")
else
    SKILLS=(critique token-aware retrospective handoff kb-search)
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

# kb-search defers its grep-first gating rule to token-aware/references/search_policy.md.
if printf '%s\n' "${SKILLS[@]}" | grep -qx "kb-search" && ! printf '%s\n' "${SKILLS[@]}" | grep -qx "token-aware"; then
    echo "  NOTE: installing kb-search without token-aware. Its search policy" >&2
    echo "        (token-aware/references/search_policy.md) is a hard dependency;" >&2
    echo "        install token-aware too, or kb-search has no gating rule." >&2
fi

mkdir -p "$DEST_DIR"
echo ""
echo "Installing to $DEST_DIR :"
for s in "${SKILLS[@]}"; do
    from="$SOURCE_DIR/$s"
    to="$DEST_DIR/$s"
    if [ -d "$to" ]; then
        cp -R "$to" "$to.bak-$STAMP"
        # Gate the removal on the backup existing, so a failed archive never
        # deletes an existing install without a copy to fall back on.
        if [ ! -d "$to.bak-$STAMP" ]; then
            echo "  ERROR: backup of $s failed; leaving existing install untouched." >&2
            exit 1
        fi
        rm -rf "$to"
        echo "  archived existing $s -> $s.bak-$STAMP"
    fi
    cp -R "$from" "$to"
    echo "  installed $s"
done

echo ""
echo "Done. Read each skill's README.md for setup steps that can't be scripted"
echo "(filling in token-aware/tools/rates.json with current, verified rates, and"
echo "reviewing handoff's reconstructed SKILL.md before relying on it)."

if printf '%s\n' "${SKILLS[@]}" | grep -qx "token-aware"; then
    echo ""
    echo "Running token-aware's test suite as a sanity check:"
    if command -v python3 >/dev/null 2>&1; then
        (cd "$DEST_DIR/token-aware/tools" && python3 -m pytest -q 2>&1 | tail -5)
    else
        echo "  SKIPPED: python3 not on PATH. Run 'python3 -m pytest -q' in token-aware/tools yourself."
    fi
fi

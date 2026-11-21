#!/usr/bin/env bash
# instrumented_skills install script (macOS / Linux)
# Run from the root of this repo. Copies each selected skill folder to
# ~/.claude/skills/<name>, archiving whatever it replaces first.
#
# Usage:
#   ./install.sh                              # installs all five skills
#   ./install.sh critique kb-search           # installs only the ones named

set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
STAMP="$(date +%Y%m%d-%H%M)"

if [ "$#" -gt 0 ]; then
    SKILLS=("$@")
else
    SKILLS=(critique retrospective handoff kb-search close-session)
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

# close-session composes retrospective/critique/handoff; it degrades gracefully without
# them (runs each missing phase's shape inline, per its own SKILL.md), so this is informational.
if printf '%s\n' "${SKILLS[@]}" | grep -qx "close-session"; then
    for companion in retrospective critique handoff; do
        if ! printf '%s\n' "${SKILLS[@]}" | grep -qx "$companion"; then
            echo "  NOTE: installing close-session without $companion. It still works," >&2
            echo "        running that phase inline at reduced quality; install $companion too" >&2
            echo "        for the full protocol." >&2
        fi
    done
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
echo "(registering retrospective's and handoff's optional hooks if you want them)."

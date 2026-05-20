#!/usr/bin/env bash
# install.sh — Crea symlinks ~/.claude/skills/<skill> → repo/skills/<skill>
# Idempotente: re-ejecutar reemplaza symlinks anteriores.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_DIR="$HOME/.claude/skills"
mkdir -p "$SKILLS_DIR"

echo "Installing skills from $REPO_DIR/skills"
echo "  Target: $SKILLS_DIR"
echo

count=0
for skill_path in "$REPO_DIR"/skills/*/; do
    skill_name="$(basename "$skill_path")"
    [ "$skill_name" = "_template" ] && continue
    target="$SKILLS_DIR/$skill_name"
    if [ -e "$target" ] || [ -L "$target" ]; then
        rm -rf "$target"
    fi
    ln -s "$skill_path" "$target"
    echo "  + $skill_name → $skill_path"
    count=$((count + 1))
done

echo
echo "✓ Installed $count skills."
echo
echo "Verify with:"
echo "  ls -la $SKILLS_DIR"

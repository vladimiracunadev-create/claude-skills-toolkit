#!/usr/bin/env bash
# uninstall.sh — Quita symlinks de ~/.claude/skills/ que apunten a este repo.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_DIR="$HOME/.claude/skills"

if [ ! -d "$SKILLS_DIR" ]; then
    echo "Nada que desinstalar — $SKILLS_DIR no existe."
    exit 0
fi

count=0
for skill_path in "$REPO_DIR"/skills/*/; do
    skill_name="$(basename "$skill_path")"
    [ "$skill_name" = "_template" ] && continue
    target="$SKILLS_DIR/$skill_name"
    if [ -L "$target" ]; then
        rm "$target"
        echo "  - $skill_name (symlink removido)"
        count=$((count + 1))
    elif [ -e "$target" ]; then
        echo "  ⚠ $skill_name existe pero NO es symlink al repo. Lo dejo por seguridad."
    fi
done

echo
echo "✓ Removed $count skills. El repo queda intacto."

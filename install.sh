#!/usr/bin/env bash
# Installs Avatar Studio for Claude Code and/or Codex, then runs setup.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Avatar Studio: $ROOT"

link_skills() {
  local dest="$1"
  mkdir -p "$dest"
  for d in "$ROOT"/skills/*/; do
    n="$(basename "$d")"
    rm -rf "$dest/$n"
    ln -s "$d" "$dest/$n"
  done
  echo "  skills linked into $dest"
}

TARGETS="${1:-all}"
if [[ "$TARGETS" == "all" || "$TARGETS" == "claude" ]]; then link_skills "$HOME/.claude/skills"; fi
if [[ "$TARGETS" == "all" || "$TARGETS" == "codex" ]];  then link_skills "${CODEX_HOME:-$HOME/.codex}/skills"; fi

"$ROOT/bin/avs" setup
echo
echo "Done. Open Claude Code or Codex and say: make me an avatar video about <topic>"

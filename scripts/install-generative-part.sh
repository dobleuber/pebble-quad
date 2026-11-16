#!/bin/sh
# Install this repository's generative-part skill for Claude Code and Codex on this machine, so it can be used
# in any project (inside this repository both find it without installing).
#
#   sh scripts/install-generative-part.sh
#
# It copies .agents/skills/generative-part to ~/.claude/skills (Claude Code) and ~/.agents/skills (Codex), and
# makes the skill's Python environment. To remove it, delete those two folders and ~/.cache/generative-part.
set -eu
source=$(cd "$(dirname "$0")/.." && pwd)/.agents/skills/generative-part
for target in "$HOME/.claude/skills" "$HOME/.agents/skills"; do
  mkdir -p "$target"
  rm -rf "$target/generative-part"
  cp -R "$source" "$target/generative-part"
  echo "installed $target/generative-part"
done
sh "$source/scripts/setup_env.sh" >/dev/null && echo "Python environment ready: $HOME/.cache/generative-part/venv"

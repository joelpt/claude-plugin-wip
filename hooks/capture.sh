#!/usr/bin/env bash
set -euo pipefail

CWD=$(python3 -c 'import sys,json; print(json.load(sys.stdin).get("cwd",""))' 2>/dev/null || echo "")
[[ -z "$CWD" ]] && CWD="$PWD"
cd "$CWD" || exit 0

WIP="./WIP.md"
DATE=$(date -u +"%Y-%m-%d %H:%M UTC")
GIT_LOG=$(git log --oneline -6 2>/dev/null || echo "(not a git repo)")
GIT_STATUS=$(git status --short 2>/dev/null || echo "")
TODO_WIP=$(grep -nE "WIP|in.progress|\[ \]" TODO.md 2>/dev/null | head -10 || echo "(no TODO.md)")

cat > "$WIP" <<EOF
# WIP — Auto-captured ($DATE)

## Recent Commits
\`\`\`
$GIT_LOG
\`\`\`

## Uncommitted Changes
\`\`\`
${GIT_STATUS:-none}
\`\`\`

## Active Tasks
\`\`\`
$TODO_WIP
\`\`\`

> Run /wip:write next session for an AI-synthesized version.
EOF

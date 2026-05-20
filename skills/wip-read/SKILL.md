---
name: wip-read
description: Load the most recent WIP recap for the current project from ~/.claude/wip/<sanitized-cwd>/. Use when SessionStart inject was skipped or you want to re-read context mid-session.
---

Locate the WIP dir: `~/.claude/wip/-<cwd-with-slashes-as-dashes>/` (e.g. cwd `/Users/joelthor/code/foo` → `~/.claude/wip/-Users-joelthor-code-foo/`).

If the dir doesn't exist, say so and suggest running `/wip:checkpoint` later this session to seed one.

Otherwise: list `*.md` files by mtime descending, Read the newest, and summarize for the user. If they ask for more history, walk further back through the list.

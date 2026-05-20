---
description: Force an immediate WIP recap synthesis for the current session. Same haiku-driven capture PreCompact and SessionEnd run automatically — use this for manual checkpoints mid-session.
---

Invoke the wip capture worker directly. This will spend a small amount of haiku tokens to update `~/.claude/wip/<sanitized-cwd>/<session-id>.md` reflecting current session state.

## Steps

1. **Locate the worker script.** Try these in order; use the first that exists:
   - `$CLAUDE_PLUGIN_ROOT/hooks/wip_hook.py` (set inside hook contexts; may or may not be set here)
   - `~/.claude/plugins/marketplaces/joelpt-claude-plugins/plugins/wip/hooks/wip_hook.py` (installed marketplace path)
   - `~/code/claude-plugin-wip/hooks/wip_hook.py` (dev checkout)

   If none exist, tell the user the plugin install is broken and stop.

2. **Determine the current session id.** Run `echo "$CLAUDE_SESSION_ID"`. If set, use it. Otherwise list `~/.claude/wip/-$(pwd | sed 's|/|-|g')/` by mtime and use the most recent `.md` basename as a fallback — and warn the user that a brand-new session with no prior capture won't yet have a file.

3. **Run the worker synchronously:**

   ```bash
   python3 "<script-path-from-step-1>" worker \
     --cwd "$(pwd)" \
     --session-id "<session-id-from-step-2>" \
     --event manual
   ```

   This blocks for ~5-10s while haiku synthesizes.

4. **Read the resulting file** (`~/.claude/wip/-$(pwd | sed 's|/|-|g')/<session-id>.md`) and surface a one-paragraph summary to the user. If empty, the worker failed silently — tell the user and suggest checking `claude --version` and that `claude -p --model haiku "hi"` works in their shell.

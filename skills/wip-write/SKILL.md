---
name: wip-write
description: Manually trigger a WIP recap synthesis for the current session — same haiku-driven capture that PreCompact / SessionEnd run automatically. Use mid-session when you want a hard checkpoint.
---

Run the capture hook in worker mode for the current session. The hook writes to `~/.claude/wip/<sanitized-cwd>/<session-id>.md`.

Prefer invoking `/wip:checkpoint` — its body handles script-path discovery and session-id fallback.

If you must invoke directly, locate the worker script via this chain (first match wins): `$CLAUDE_PLUGIN_ROOT/hooks/wip_hook.py`, `~/.claude/plugins/marketplaces/joelpt-claude-plugins/plugins/wip/hooks/wip_hook.py`, `~/code/claude-plugin-wip/hooks/wip_hook.py`. Then:

```bash
python3 "<script>" worker --cwd "$(pwd)" --session-id "$CLAUDE_SESSION_ID" --event manual
```

If `$CLAUDE_SESSION_ID` isn't set, fall back to the newest `.md` file in `~/.claude/wip/-$(pwd | sed 's|/|-|g')/` (use its basename sans `.md`).

After it returns, Read the written file and summarize what changed.

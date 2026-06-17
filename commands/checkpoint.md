---
description: Generate WIP recap of this session
model: haiku
---

Worker: !`for f in "${CLAUDE_PLUGIN_ROOT}/hooks/wip_hook.py" ~/.claude/plugins/marketplaces/joelpt-claude-plugins/plugins/wip/hooks/wip_hook.py ~/code/claude-plugin-wip/hooks/wip_hook.py; do [ -f "$f" ] && echo "$f" && break; done`
Session: !`echo "$CLAUDE_CODE_SESSION_ID"`
WIP dir: !`echo ~/.claude/wip/-$(pwd | sed 's|^/||;s|/|-|g')`

If Worker is empty, the plugin is not installed — tell the user and stop.
If Session is empty, run `ls -t <WIP dir>/ 2>/dev/null | head -1 | sed 's|\.md||'` for the session ID.

Run the worker synchronously (~10s):

```bash
python3 <Worker> worker --cwd "$(pwd)" --session-id <Session> --event manual
```

Read `<WIP dir>/<Session>.md` and surface a one-paragraph summary.

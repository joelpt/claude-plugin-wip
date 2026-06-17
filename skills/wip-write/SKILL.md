---
name: wip-write
description: Checkpoint WIP recap now
---

Prefer `/wip:checkpoint` — its body has pre-populated script path and session ID.

If invoking directly:

Worker: !`for f in "${CLAUDE_PLUGIN_ROOT}/hooks/wip_hook.py" ~/.claude/plugins/marketplaces/joelpt-claude-plugins/plugins/wip/hooks/wip_hook.py ~/code/claude-plugin-wip/hooks/wip_hook.py; do [ -f "$f" ] && echo "$f" && break; done`
Session: !`echo "$CLAUDE_CODE_SESSION_ID"`
WIP dir: !`echo ~/.claude/wip/-$(pwd | sed 's|^/||;s|/|-|g')`

If Session is empty, run `ls -t <WIP dir>/ 2>/dev/null | head -1 | sed 's|\.md||'` for the fallback.

```bash
python3 <Worker> worker --cwd "$(pwd)" --session-id <Session> --event manual
```

After it returns, Read `<WIP dir>/<Session>.md` and summarize what changed.

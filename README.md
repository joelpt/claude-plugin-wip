# wip

Work-in-progress session handoff for Claude Code.

- Auto-injects `WIP.md` into context on a fresh session start.
- Captures task state on `SessionEnd` and `PreCompact` so the next session resumes seamlessly.

## Install

```bash
claude plugin marketplace add joelpt/joelpt-claude-plugins
claude plugin install wip@joelpt-claude-plugins
```

Then restart Claude Code. Requires read access to the private marketplace repo (`gh auth login`).

## Layout

```text
.claude-plugin/plugin.json   ← plugin manifest
hooks/                       ← SessionStart / SessionEnd / PreCompact capture
skills/wip-read, wip-write   ← read & write WIP.md
```

This plugin is distributed via the [`joelpt-claude-plugins`](https://github.com/joelpt/joelpt-claude-plugins)
marketplace. Bump `.claude-plugin/plugin.json` `version` (patch minimum) on any change — the
marketplace cache is keyed by version.

## License

MIT. See `LICENSE`.

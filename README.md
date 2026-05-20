# wip

Session-rolling WIP recaps for Claude Code. Survives compactions; resumes across sessions.

## What it does

- **SessionStart**: if the current session-id matches an existing recap, inject it (resumption). Otherwise inject the most recent 5 session recaps for this cwd. Prune anything beyond the most recent 10.
- **Stop** (debounced, 10 min): kick off a backgrounded Haiku call to update the current session's recap.
- **PreCompact**: same capture, before context compaction wipes the transcript.
- **SessionEnd**: same capture, on natural session termination.
- **`/wip:checkpoint`**: manual on-demand recap (synchronous).
- **`/wip:read`**, **`/wip:write`**: skills for reading the latest recap or forcing a synth.

## Layout

```
~/.claude/wip/
  -Users-joelthor-code-<project>/
    <session-id>.md       # one per session, appended across compactions
```

The "Done this session" section is *intended* to be append-only across captures within a session — so even if compaction drops the early transcript, the list of completed items should survive. Append-only is currently enforced via model instruction (the worker prompts Haiku to preserve and append), not by post-processing in code; Haiku may occasionally rewrite the block. Hardening this to a code-enforced merge is on the v2 list. "Known next steps" and "Notes" are replaced each turn (current understanding only).

## Plugin layout

```text
.claude-plugin/plugin.json   ← manifest (CalVer: YYYY.MM.DD.N)
hooks/wip_hook.py            ← single Python entry point: inject/capture/worker
hooks/hooks.json             ← SessionStart, Stop, PreCompact, SessionEnd wiring
skills/wip-read              ← load latest recap
skills/wip-write             ← manual synth (same as /wip:checkpoint)
commands/checkpoint.md       ← /wip:checkpoint slash command
```

## Install

```bash
claude plugin marketplace add joelpt/joelpt-claude-plugins
claude plugin install wip@joelpt-claude-plugins
```

Restart Claude Code. Requires read access to the private marketplace repo (`gh auth login`).

## Cost

Each Haiku call is small (~few thousand input tokens after transcript-tail, ~few hundred output). Expected per-session spend with default config: pennies. PreCompact and SessionEnd run once per session each; Stop debounces to one call per 10 minutes worst-case.

## License

MIT. See `LICENSE`.

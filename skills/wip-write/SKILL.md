---
name: wip-write
description: Write (or replace) WIP.md with an AI-synthesized session handoff covering current task state, blockers, recent commits, and concrete next actions. Use when ending a work session or before context gets lost.
---

Write `./WIP.md` capturing exactly where we are. Gather: `git log --oneline -10`, `git status`, TODO.md, LEARNINGS.md if present.

Sections:
1. **Status** — 1-2 sentence summary
2. **Recent Commits** — last 6 with WHY each was needed
3. **Active Tasks** — what was in-progress
4. **Key Findings** — non-obvious discoveries this session
5. **Blockers** — with evidence
6. **Next Actions** — first 3 concrete next steps

Keep under 80 lines.

---
description: Show current project state — dashboard + recent commits + pending tasks
---

Read these files and report a tight status to the user. Do not edit anything.

1. `SESSION_STATE.md` — the rolling dashboard (primary source)
2. Output of `git log --oneline -10` — recent commits
3. `context/TASKS.md` — the Phase 2b + next-up items

Then produce a concise report with sections:
- **Where we are** (1-2 sentences, from SESSION_STATE.md "Current focus")
- **Last 5 commits** (titles only)
- **In progress / partial** (from SESSION_STATE.md)
- **Blocked** (from SESSION_STATE.md)
- **Suggested next** (top 3 from "Next up")
- **Watch-outs** (from SESSION_STATE.md "Watch-outs" — abbreviated)

Keep the whole report under 30 lines. This is the passenger-check-in — tight, scannable, no preamble.

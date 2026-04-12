---
description: Session opener — load current state, then ask the user what to work on
---

Session starting. Do NOT edit anything yet. Execute in order:

1. **Load state.** Read:
   - `SESSION_STATE.md` (rolling dashboard)
   - `git log --oneline -10` (recent commits)
   - `memory/regressions.md` (incidents to avoid repeating — just scan)

2. **Report a 3-part briefing to the user:**

   **Where we are:** 1 sentence from SESSION_STATE.md "Current focus."

   **Suggested next (top 3):** from SESSION_STATE.md "Next up" — list with IDs, titles, estimated effort, and one-sentence rationale each.

   **Any alert:** if `memory/regressions.md` has an open incident relevant to what's next, or if `SESSION_STATE.md` "Blocked" has something that might need user action before we can start.

3. **Ask the user:** "What are we doing this session?" — and offer the top suggestion as the default.

4. **Wait for the user's choice** before touching any code or files.

5. Once the user chooses, if the task is non-trivial (3+ files or ambiguous), propose a short plan first (2-5 bullets) and wait for approval before implementing.

Keep the whole briefing under 25 lines. Passenger-awake-check, not full audit.

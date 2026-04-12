---
description: End-of-session — update SESSION_STATE.md with what changed, propose a commit
---

The session is ending. Execute this sequence:

1. **Summarize what happened this session.** Briefly — what changed, what was decided, what's now pending.

2. **Update `SESSION_STATE.md`:**
   - Update the "Last updated" timestamp to today's date (absolute — convert any relative dates).
   - Move completed items from "In progress" to "Done (recent)". Keep the Done list to the 10 most recent items; archive older entries by removing.
   - Add any new "In progress / partial" items with their completion %.
   - Update "Blocked / pending external action" if new blockers appeared.
   - Update "Next up" — re-rank by leverage; add new items; remove done ones.
   - Add to "Key recent decisions" if a new ADR was created or a significant call was made.
   - Leave "Watch-outs" mostly stable — only edit if a new systemic risk emerged.

3. **Review `git status`** — list uncommitted changes by logical cluster. Propose a commit plan:
   - Group files by concern (docs vs code vs config vs session-log).
   - Draft one commit message per cluster.
   - Ask the user: "Commit all? Commit some? Skip?"

4. **If the user approves commit**, execute the commits with the proposed messages. Use focused messages that explain the *why*, not the *what*.

5. **Remind the user** (if applicable) of:
   - Any Blocked items requiring their action (e.g. Cline uninstall, B2 credentials).
   - The top 1 item from "Next up" as a suggested next session.

Do not `git push` unless explicitly asked. Do not create PRs unless explicitly asked.

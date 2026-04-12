# Research: Claude Code Workflows for Long, Complex Projects

**Date:** 2026-04-12
**Depth:** Deep dive
**Query:** How experienced teams and solo developers run long, complex software projects with Claude Code without context window bloating — concrete, verifiable patterns.

---

## TLDR

The single most-recommended pattern from Anthropic and its engineers is **short, focused sessions with persistent state in git-tracked files** — not one long session. The initializer-then-coding-agent loop (Anthropic engineering blog, Nov 2025) externalizes all state to `claude-progress.txt` and git history, giving every fresh session a complete handoff in seconds. The most-warned-against anti-pattern is the inverse: treating Claude Code like a stateful assistant, letting context accumulate across unrelated tasks, and embedding session state inside a bloated `CLAUDE.md` — at the cost of instruction compliance collapse past ~150–200 effective rules.

---

## Executive Summary

Anthropic's official documentation, Boris Cherny's public workflow posts, and the broader community have converged on a consistent set of principles for complex, multi-session projects: treat each session like a git branch (focused, bounded, committed), externalize all state to files rather than LLM memory, use subagents to keep the main context clean for reasoning, and compact proactively at task boundaries rather than reactively when the window is almost full. The most dangerous failure mode is the "kitchen sink session" — a single long conversation that accumulates irrelevant history until instruction compliance degrades and hallucinations increase. For a 60-task multi-phase project like this one, the state of the art is not one orchestration tool but a combination of: a tight `CLAUDE.md` (under 3 KB), a separate per-phase plan file, a `claude-progress.txt`-style session log updated by Claude at every session end, and worktree-isolated parallel sessions for independent tasks.

---

## 1. Anthropic's Official Recommended Patterns

**Source:** [Best Practices for Claude Code](https://code.claude.com/docs/en/best-practices) — accessed 2026-04-12

### CLAUDE.md: Structure and Scope

Anthropic is explicit about three scope levels:

- `~/.claude/CLAUDE.md` — applies to all sessions globally; put universal preferences here
- `./CLAUDE.md` (project root) — check into git; team-shared project conventions
- `./CLAUDE.local.md` — personal project overrides; add to `.gitignore`
- Child directories: Claude pulls in subdirectory `CLAUDE.md` files on demand

The `@path/to/file` import syntax lets you compose: `@docs/git-instructions.md` imports that file's content on load. This lets you keep the root file short and import domain-specific context only when needed. [^1]

**What to include vs. exclude:**

| Include | Exclude |
|---|---|
| Bash commands Claude can't guess | Anything Claude can read from code |
| Code style rules that differ from defaults | Standard language conventions |
| Testing instructions and preferred test runners | Detailed API docs (link instead) |
| Architectural decisions specific to your project | Information that changes frequently |
| Developer environment quirks, required env vars | File-by-file codebase descriptions |
| Common non-obvious gotchas | Self-evident practices like "write clean code" |

**Key constraint:** There is roughly a 150–200 *effective instruction budget* before compliance drops off, and the system prompt already consumes ~50 of those slots. Every unnecessary line dilutes the ones that matter. If Claude keeps violating a rule, the file is probably too long and the rule is getting lost. Ruthlessly prune. [^1]

### When to Use Subagents vs. Main Session vs. Separate Sessions

From the official docs [^1] [^2]:

- **Subagents** (`.claude/agents/`): Use when a side task would flood your main context with search results, logs, or file contents you won't reference again. "Use subagents to investigate X" — the subagent reads dozens of files in its own context and reports back only a summary. Each subagent has its own context window, custom system prompt, tool restrictions, and independent permissions.
- **Separate sessions** (`claude --continue` / `claude --resume`): Use for distinct workstreams. Treat sessions like branches — different features or phases get separate, persistent contexts. Rename sessions descriptively: `/rename oauth-migration`.
- **Main session**: Reserve for reasoning and planning. Do not pollute it with bulk file reads, scraping, or exploratory investigation — delegate those.

Quote from the official docs: *"Use a subagent to investigate how our authentication system handles token refresh... The subagent explores the codebase, reads relevant files, and reports back with findings — all without cluttering your main conversation."* [^1]

### Context Compaction: /compact vs /clear vs Session Restart

Three mechanisms, each appropriate in different situations [^1]:

1. **`/clear`**: Resets the context window entirely. Use between *unrelated tasks* — the most aggressive and cleanest option. Quote: *"If you've corrected Claude more than twice on the same issue in one session, the context is cluttered with failed approaches. Run `/clear` and start fresh."*

2. **`/compact [instructions]`**: Summarizes older conversation while preserving key context. Run proactively at task *boundaries*, not when the window is 90% full. Example: `/compact Focus on the API changes`. You can also customize compaction behavior in CLAUDE.md: *"When compacting, always preserve the full list of modified files and any test commands."*

3. **`/rewind` / Esc+Esc**: Opens checkpoint menu — restore conversation only, code only, or both. Every Claude action creates a checkpoint automatically.

4. **`--continue` / `--resume`** (session restart): For multi-day work. Claude saves sessions locally; `--continue` resumes the most recent; `--resume` lets you pick from recent sessions.

**Proactive compaction heuristic** (community): Run `/compact` after completing a meaningful milestone, not after filling the window. The community-observed degradation thresholds: precision drops at ~70% context, hallucinations increase at ~85%, responses become erratic at 90%+. [^12]

### Skills, Slash Commands, Hooks — When Each Is Appropriate

**Skills** (`.claude/skills/<name>/SKILL.md`): Domain knowledge and reusable workflows. Use for context that only matters *sometimes* — Claude loads them on demand, keeping CLAUDE.md lean. Example: API conventions, a full deploy workflow, a fix-issue script. Skills invoke with `/skill-name`. Note: one evaluation found agents invoked skills in only 56% of relevant cases — never rely on skills for *critical* path instructions. [^1] [^16]

**Slash commands** (`.claude/commands/`): Inner-loop, high-frequency workflows you run many times per day. Boris Cherny: *"I use slash commands for every 'inner loop' workflow I do many times a day. This saves me from repeated prompting, and makes it so Claude can use these workflows too. Commands are checked into git and live in `.claude/commands/`."* [^4] Example: `/commit-push-pr` (pre-computes git status inline to avoid back-and-forth). Add `disable-model-invocation: true` for workflows with side effects.

**Hooks**: Deterministic guarantees. Unlike CLAUDE.md instructions (advisory), hooks run scripts at specific lifecycle events regardless of model behavior. Use for: running eslint after every file edit, blocking writes to the migrations folder, re-injecting context after compaction, logging modified files. Lifecycle events: `SessionStart`, `PreToolUse`, `PostToolUse`, `PreCompact`, `UserPromptSubmit`, `SubagentStop`. [^1]

### Handoff Between Sessions

Anthropic's own engineering practice (from the harness blog posts [^6] [^7]) is the clearest public signal:

- A **`claude-progress.txt`** file maintained by the agent at the end of every coding session. It records: what features are done, what's in-progress, what's next, and key decisions made.
- **Git history** as the authoritative record of what was actually built.
- At each new session start, the agent reads the progress file and git log before doing anything else.

The official Claude Code docs reference `claude --continue` for resuming sessions, and note that session history is saved locally. The `/rename` command lets you give sessions descriptive names for retrieval. [^1]

### Git Worktrees for Parallel Work Streams

This is described as *the single biggest productivity unlock* by the Claude Code team [^4]:

- Each parallel workstream gets its own git worktree: an isolated checkout on a separate branch
- Multiple Claude sessions run simultaneously without file conflicts
- Boris Cherny runs 5 local worktrees + 5–10 browser sessions concurrently
- The `claude -w` flag creates an isolated git worktree per task automatically

From the official docs: *"Claude Code desktop app: Manage multiple local sessions visually. Each session gets its own isolated worktree."* [^1]

---

## 2. What Anthropic Engineers Have Said Publicly

### Boris Cherny (Creator of Claude Code)

Source: [How Boris Uses Claude Code](https://howborisusesclaudecode.com) and his Threads posts [^3] [^4] — accessed 2026-04-12

Key quotes and practices:

- **"My setup might be surprisingly vanilla. Claude Code works great out of the box, so I personally don't customize it much."** He does not run a complex orchestration layer.

- **Worktrees as the top tip**: *"I spin up 3–5 git worktrees at once, each running its own Claude session in parallel. It's the single biggest productivity unlock."* He runs 5 terminal sessions + 5–10 browser sessions simultaneously.

- **CLAUDE.md at Anthropic**: The team maintains a single CLAUDE.md in git. *"Anytime we see Claude do something incorrectly, we add it to CLAUDE.md so Claude knows not to do it next time. I often use the `@.claude` tag on coworkers' PRs to add learnings."* Their CLAUDE.md is currently ~2,500 tokens.

- **Slash commands for every inner loop**: All commands live in `.claude/commands/` and are checked into git. His daily `/commit-push-pr` uses inline bash to pre-compute git status.

- **Plan first, execute once**: *"Start every complex task in plan mode. Pour your energy into the plan so Claude can 1-shot the implementation."*

- **50–100 PRs per week** velocity, primarily through parallel worktree sessions.

### Anthropic Engineering Blog — C Compiler Project

Source: [Building a C compiler with a team of parallel Claudes](https://www.anthropic.com/engineering/building-c-compiler) — 2025 [^5]

- 16 agents ran in parallel writing a Rust-based C compiler capable of compiling the Linux kernel
- Produced ~100,000 lines of code across nearly 2,000 Claude Code sessions
- Each session was short and isolated; state was passed via files and git

### Anthropic Engineering Blog — Long-Running Agent Harnesses

Source: [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) — November 26, 2025 [^6]
Source: [Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps) — March 2026 [^7]

**Nov 2025 — Initializer + Coding Agent pattern:**
- **Initializer agent**: writes a feature list JSON, an `init.sh`, a `claude-progress.txt`, and makes an initial git commit. Features start marked "failing."
- **Coding agent loop**: every new session reads `claude-progress.txt` + git log, runs end-to-end tests, picks one feature, implements it, commits, updates `claude-progress.txt`.
- Key insight: *"The key was finding a way for agents to quickly understand the state of work when starting with a fresh context window."* [^6]

**March 2026 — Three-agent architecture:**
- **Planner**: decomposes a product spec into discrete, tractable chunks with enough context for a fresh agent to execute cold
- **Generator**: builds the code in a single context window per task, hands off structured artifacts (JSON feature specs, commit-by-commit progress log) to next session
- **Evaluator**: grades output using predefined criteria; for frontend work uses Playwright MCP to navigate live pages. Separate from generator because *"AI models are poor critics of their own output — agents tend to confidently praise work even when quality is obviously mediocre."* [^7]

**On context resets**: *"Claude Sonnet 4.5 exhibited context anxiety strongly enough that compaction alone wasn't sufficient to enable strong long task performance — context resets became essential to the harness design."* [^7]

---

## 3. Public Repos with Sophisticated Agent Workflows

### Repo 1: gsd-build/get-shit-done
**URL:** [https://github.com/gsd-build/get-shit-done](https://github.com/gsd-build/get-shit-done) — accessed 2026-04-12 [^8]

Philosophy: "The complexity is in the system, not in your workflow."

- Generates `USER-PROFILE.md`, `PROJECT.md`, `REQUIREMENTS.md`, `ROADMAP.md`, `STATE.md`
- `STATE.md` tracks current phase/task and is updated by `/gsd:ship` after every commit
- `/gsd auto` autonomous mode: researches, plans, executes, verifies, commits, advances through every task slice until a milestone is complete
- Context engineering uses XML-formatted prompts and subagent orchestration internally
- Roadmaps are intentionally short: one or two sentences per phase (not ticket-level detail)
- Actively maintained as of April 2026 (gsd-2 is the current version)

**Convention**: `STATE.md` is the single source of truth for "where are we now." CLAUDE.md is kept minimal. Skills handle domain knowledge. `/gsd:ship` automatically updates `STATE.md` and generates the PR body from planning artifacts.

### Repo 2: parcadei/Continuous-Claude-v3
**URL:** [https://github.com/parcadei/Continuous-Claude-v3](https://github.com/parcadei/Continuous-Claude-v3) — accessed 2026-04-12 [^9]

Solves the session continuity problem with hooks:

- **Continuity ledger**: `CONTINUITY_CLAUDE-<session>.md` — goal, constraints, what's done, what's next, key decisions. Loads automatically after `/clear` via hooks.
- **Handoff files**: created at session end with file:line references, learnings, patterns, next steps. Loaded at session start.
- **Hook lifecycle coverage**: `SessionStart` (loads ledger + latest handoff), `PreCompact` (creates auto-handoff before compaction), `PostToolUse` (tracks modified files), `SubagentStop`
- 32 specialized agents, 30 lifecycle hooks, 109 modular skills
- Includes a 5-layer code analysis system (AST, call graph, control flow, data flow, PDG slicing)

**Convention**: Hooks are the backbone of continuity — they fire automatically at lifecycle events without relying on the model remembering to do anything.

### Repo 3: automazeio/ccpm
**URL:** [https://github.com/automazeio/ccpm](https://github.com/automazeio/ccpm) — accessed 2026-04-12 [^10]

Uses **GitHub Issues as the single source of truth** — avoiding the markdown drift problem:

- PRD → epic GitHub Issue → sub-issues per task (all via slash command)
- Tasks marked `parallel: true` run concurrently across worktrees without conflicts
- CCPM creates a dedicated worktree per epic: `../epic-notification-system/`
- Generates a mapping file: local file ↔ GitHub Issue number ↔ worktree path
- Design philosophy: *"Every line of code is traceable back to a spec."*

**Convention**: GitHub Issues replace markdown task boards. No drift because the issue tracker is the state, not a file Claude might misread or overwrite.

### Repo 4: claude-task-master (eyaltoledano)
**URL:** [https://github.com/eyaltoledano/claude-task-master](https://github.com/eyaltoledano/claude-task-master) — accessed 2026-04-12 [^11]

25,300 stars as of January 2026. Most widely adopted orchestration tool in the Claude Code ecosystem.

- Input: PRD at `.taskmaster/docs/prd.txt`
- Output: `tasks.json` with tasks, dependencies, complexity scores, subtasks
- Can generate individual Markdown `.md` files per task from the JSON
- 49 slash commands: `/taskmaster:parse-prd`, `/taskmaster:next-task`, `/taskmaster:update-task`, etc.
- `autopilot` mode (since v0.30.0): generate test → implement → verify → commit → repeat
- Works as an MCP server: connects to Cursor, Windsurf, Roo, Claude Code

**Known limitation**: Dual source of truth risk if you edit task markdown files separately from the JSON. The JSON is authoritative; markdown files are generated views.

### Repo 5: shihchengwei-lab/claude-code-session-kit
**URL:** [https://github.com/shihchengwei-lab/claude-code-session-kit](https://github.com/shihchengwei-lab/claude-code-session-kit) — accessed 2026-04-12 [^13]

Battle-tested context monitoring and handoff templates from 92 real sessions:

- Three-tier context alerts: 40% / 60% / 70% utilization
- Hard stop at 70% — forces handoff file creation
- Standardized handoff format: completed tasks, pending tasks, context notes, file:line references
- Session startup hook loads `session-state.md` automatically

---

## 4. Orchestration Layer Comparison

| Tool | What it solves | Known failure modes | Status (2026) |
|---|---|---|---|
| **Cline Kanban** | Visual multi-agent orchestration UI on top of Cline; each task is a Markdown file in `.agentkanban/tasks/` | Dual source of truth drift when agents overwrite task files; markdown state and LLM state diverge across sessions | Active; v3.25 added "Focus Chain" (re-injects todo list into context at intervals to prevent drift) [^14] |
| **claude-squad** (smtg-ai) | Terminal app managing multiple agents (Claude Code, Codex, Aider, Amp) simultaneously with tmux isolation + worktrees | Alpha software — APIs/CLI may change; SDK-first mode is "experimental and buggy"; tmux timeout errors requiring version sync | Active; 5.8K stars; not production-stable [^15] |
| **Task Master AI** (eyaltoledano) | PRD → structured JSON task graph with dependencies, complexity scores; 49 slash commands | If markdown task files are edited manually, JSON becomes stale (JSON is the real source of truth); agent invokes skills only ~56% of the time in some evals | Active; 25K+ stars; most widely adopted [^11] |
| **Backlog.md** (MrLesk) | Markdown-native task manager + Kanban visualizer; stores tasks as `.md` files with YAML frontmatter in `backlog/` or `.backlog/`; MCP integration | Human-readable but agents can overwrite carefully crafted acceptance criteria; requires discipline to keep tasks atomic | Active; MIT; designed for AI-human collaboration [^17] |
| **CCPM** (automazeio) | GitHub Issues as authoritative task state; worktree-per-epic isolation; full traceability PRD→code | Requires GitHub repo; heavier setup than pure-markdown approaches; no offline mode | Active; production-oriented [^10] |
| **Continuous-Claude** (parcadei) | Hooks-based continuity: ledgers + handoffs fire at lifecycle events, not relying on model memory | High complexity (32 agents, 30 hooks, 109 skills) — overkill for small projects; v2→v3 migration broke some hooks | Active (v3 is current); last updated January 2026 [^9] |
| **GSD** (gsd-build) | Lightweight meta-prompting + spec-driven system; `STATE.md` tracks current position; `/gsd auto` for autonomous execution | Less structure than CCPM for large teams; state in `STATE.md` must be kept updated by model or it drifts | Active; April 2026 updates; solo-developer oriented [^8] |
| **Roo Code** | VS Code extension forked from Cline; multi-protocol orchestration; bridges MCP with non-Anthropic models | VS Code bound; orchestration model different from terminal-first Claude Code; separate ecosystem | Active; 22K stars; 1.2M installs [^18] |
| **Native Agent Teams** (Anthropic) | Officially supported multi-agent coordination in Claude Code: shared task list with dependencies, peer-to-peer messaging, file locking | Experimental; disabled by default; enable via `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` env var | Shipped Feb 6, 2026 alongside Opus 4.6; experimental status [^19] |

**What raw Claude Code lacks that these tools add:**
- Persistent task state across sessions (native Claude Code has no built-in task board)
- Automatic handoff file creation at session end
- Parallel worktree coordination (native `-w` flag exists but no orchestration layer)
- Dependency tracking between tasks

---

## 5. Context Window Hygiene — Specific Techniques

### Structured Handoff Files

The Anthropic harness pattern [^6] is the clearest template:

```
claude-progress.txt
---
DONE: Feature A (commit abc123), Feature B (commit def456)
IN PROGRESS: Feature C — auth callback handler, 60% complete
BLOCKED: Feature D — waiting on Feature C
NEXT: Feature E, Feature F (parallelizable)
KEY DECISIONS: Using JWT not sessions (ADR-001); SQLite for dev, Postgres for prod
LAST SESSION: [ISO timestamp]
```

Every new session reads this file before touching any code. Every session end, Claude updates it.

Community tools have standardized this further:
- `SESSION_STATE.md`: current task, context notes, working files with line refs
- `HANDOFF.md`: "necessary and sufficient" context for a cold session to pick up seamlessly [^13]
- Continuity ledger in Continuous-Claude [^9]: goal + constraints + done + next + decisions

### Progressive Summarization

The pattern: write a tight summary at end of session, load it at start of next.

- Before ending a session: *"Summarize what we accomplished, what's blocked, what the next 3 tasks are, and any non-obvious decisions made. Write this to `PROGRESS.md`."*
- At next session start: *"Read `PROGRESS.md` and our git log. What are we working on?"*
- Keep the summary file under 200 lines — it's a navigation aid, not a full log

### Strategic /compact Timing

From the official docs and community [^1] [^12]:

- **Too late**: waiting until Claude warns you the context is nearly full (by then, efficiency already degraded)
- **Right time**: at a natural task boundary — after committing a feature, after completing an investigation, after finishing a phase
- **Explicit instructions**: `/compact Focus on the authentication changes and skip the scraper refactor`
- In CLAUDE.md: *"When compacting, always preserve the full list of modified files, any test commands, and current task context"*
- Community heuristic: compact at 60% utilization, not 90%

### ADRs as Context-Compression Tools

ADRs (Architecture Decision Records) are gaining traction as a way to keep CLAUDE.md small [^20]:

- Each significant decision gets its own file: `context/decisions/ADR-001-jwt-vs-sessions.md`
- CLAUDE.md imports only the index: `@context/decisions/`
- Claude reads relevant ADRs on demand, not all at once
- One developer reported reducing CLAUDE.md to under 2 KB by moving all architectural context to ADRs
- Research note: ETH Zürich found developer-written CLAUDE.md files improve task success by ~4% but add 20–23% inference cost because agents follow every instruction including irrelevant ones [^16]

### Separate Agents Per Concern

From the Anthropic three-agent harness [^7] and community practice:

- **Research agent**: explores codebase, reads files, investigates options — runs in own context, reports summary
- **Implementation agent**: executes against a spec, focused context on one feature/task
- **Review agent**: fresh context, no bias toward code it just wrote; runs after implementation

The Writer/Reviewer pattern from official docs [^1]:
- Session A: `Implement a rate limiter for our API endpoints`
- Session B: `Review the rate limiter in @src/middleware/rateLimiter.ts — look for edge cases, race conditions, and consistency with existing patterns`
- Session A: `Here's the review feedback: [Session B output]. Address these issues.`

---

## 6. Anti-Patterns: What the Community Warns Against

### 1. The Kitchen Sink Session
**What it is**: Starting one task, asking something unrelated, going back to the first task. Context fills with irrelevant information.
**Official warning**: *"If you've corrected Claude more than twice on the same issue in one session, the context is cluttered with failed approaches. Run `/clear` and start fresh with a more specific prompt."* [^1]

### 2. Storing State in the LLM
**What it is**: Relying on Claude to "remember" decisions across `/clear` or session restarts. There is no persistent LLM memory — re-reading instructions happens every time.
**Community warning**: *"There is no magic database or long-term learning in Claude Code — LLMs do not 'remember' in a human sense but re-read instructions every time."* [^16]
**Fix**: State always lives in files (git-tracked), never in the LLM's context.

### 3. Bloated CLAUDE.md
**What it is**: CLAUDE.md grows to 500+ lines with everything documented.
**Official warning**: *"Bloated CLAUDE.md files cause Claude to ignore your actual instructions. If Claude keeps doing something you don't want despite a rule, the file is probably too long."* [^1]
**Quantified limit**: Keep under 3,000 tokens (~2,000 words). ETH Zürich research showed LLM-generated CLAUDE.md files (as opposed to human-written) *reduce* task success by ~3% while adding 20–23% inference cost. [^16]
**Fix**: Ruthlessly prune. Move domain knowledge to skills. Move stable decisions to ADRs. Move workflow steps to slash commands.

### 4. Correction Loop Without Reset
**What it is**: Claude does something wrong, you correct it, it's still wrong, you correct again. After two corrections, start fresh.
**Official warning**: *"A clean session with a better prompt almost always outperforms a long session with accumulated corrections."* [^1]

### 5. Infinite Exploration
**What it is**: Asking Claude to "investigate X" without scope. Claude reads hundreds of files, filling your main context.
**Fix**: *"Scope investigations narrowly or use subagents so the exploration doesn't consume your main context."* [^1]

### 6. One Session for a Month / Week-Long Sessions
**What it is**: Using a single Claude Code session for an entire multi-week project phase.
**Community warning**: *"Treating Claude Code as one long continuous conversation leads to large, sprawling sessions that accumulate irrelevant context. Treat sessions like git commits — when you finish a meaningful unit of work, close the session and start fresh."* [^12]
**Quantified threshold**: Performance degradation begins at ~70% context window; at 90%+ responses become erratic [^12]

### 7. Using CLAUDE.md as a Session Log
**What it is**: Updating CLAUDE.md with current session state (what task you're on, what you've tried).
**Warning**: *"Updating CLAUDE.md with session state means the file will carry those assumptions into future sessions. Review it periodically to remove stale entries."* [^13]
**Fix**: Use a separate `PROGRESS.md` or `claude-progress.txt` for session state.

### 8. Dual Source of Truth (the Cline Kanban / Markdown Drift problem)
**What it is**: Maintaining both a markdown task file AND a separate state representation (Kanban board, JSON, etc.). They diverge.
**Community signal**: Cline Kanban's v3.25 explicitly added "Focus Chain" to address this — re-injecting the todo list into context at regular intervals because agents forget state [^14]. CCPM's answer is GitHub Issues as the *only* source of truth [^10].
**Fix**: Choose one source. GitHub Issues (via CCPM) or JSON (via Task Master) are more robust than pure markdown because they have structured schemas that resist freeform overwriting.

---

## 7. The "10-Task Problem": What Pattern Would a Senior Anthropic Engineer Follow?

**Based on the evidence above** — not invented.

For a well-defined list of 10 engineering tasks with dependencies to complete over a week, the pattern closest to what Boris Cherny and the Anthropic harness team describe:

**Phase 0 — Before touching code (30 minutes)**
1. Write a PRD or spec for the week's work. Keep it in a file: `.taskmaster/docs/prd.txt` or `context/plans/week-N.md`.
2. Use Plan Mode (Ctrl+Shift+P) to have Claude decompose it into a task list. Review and edit the plan in your text editor before proceeding.
3. Create `claude-progress.txt` with all 10 tasks listed as "pending."

**Per-task execution**
4. Start a fresh session (or worktree) per task. Do not carry context from task 1 into task 3.
5. Session opener: *"Read claude-progress.txt and our git log. We're implementing Task 4."*
6. Use Plan Mode first if the task is ambiguous or touches 3+ files.
7. When done: commit, then have Claude update `claude-progress.txt`: status → done, key decisions made, files modified.

**For parallelizable tasks**
8. Spin up separate git worktrees (`claude -w` or manually). Run 2–3 sessions simultaneously.
9. Each worktree gets its own branch. Merge when both sessions complete and pass tests.

**Session hygiene**
10. `/clear` between tasks in the same session (if reusing a session). `/compact` at natural midpoints if working on a large task.
11. Reviewer pattern for significant output: after implementation, start a *fresh* session to review what was built — no context bias.

**No strong public signal on**: Whether to use Task Master AI vs. raw markdown for the task list at this scale (10 tasks / 1 week). Boris Cherny's setup is "surprisingly vanilla" and doesn't use a dedicated orchestration tool. The Anthropic harness papers deal with fully autonomous multi-hour runs, not weekly human-in-the-loop work. The most honest answer for a solo developer with 10 well-defined tasks: plain `claude-progress.txt` + git worktrees + fresh sessions per task is close to what the evidence points to, and it's lighter than any orchestration layer.

---

## What This Project Should Adopt

This project (solo founder, ~60 tasks across 6 phases, Python pipeline) maps well to the available evidence. Specific, actionable recommendations:

### Immediate (no tooling change required)

**1. Create `claude-progress.txt` in the project root.** One entry per task with status (pending / in-progress / done / blocked). Claude updates it at every session end. This replaces the implicit session memory you've been relying on and directly applies the Anthropic harness pattern. [^6]

**2. Trim CLAUDE.md aggressively.** The current `CLAUDE.md` is well-structured but examine every line: does Claude make a mistake without it? Move everything about the knowledge graph build to a skill or ADR. Keep CLAUDE.md under 100 lines / ~1,500 tokens. [^1]

**3. One task per session, full stop.** Given 6 phases and ~60 tasks, each session should be scoped to a single task or a single coherent cluster of related subtasks. Close and restart rather than accumulating context.

**4. `/compact` at phase boundaries.** When finishing Phase 2 (KG assembly) and moving to Phase 3 (training), compact with explicit instructions: `/compact Preserve: current phase status, data paths, schema decisions, test commands. Discard: scraper debug output, intermediate file reads.`

### Medium-term (small setup investment)

**5. Migrate task tracking to GitHub Issues + CCPM or Task Master AI.** The Cline Kanban + markdown drift problem you experienced is well-documented and well-understood. Both CCPM (GitHub Issues as truth) and Task Master AI (JSON as truth) solve this with a structured schema. Given you're already on git, CCPM maps most naturally to your existing workflow. [^10] [^11]

**6. Add 2–3 skills files.** The current `CLAUDE.md` contains architectural context about scrapers, knowledge graph, and training. Move these to `.claude/skills/`: `kg-architecture.md`, `training-pipeline.md`, `scraper-patterns.md`. Claude loads them on demand. [^1]

**7. Formalize handoff at phase boundaries.** At the end of each phase, have Claude write a `context/plans/phase-N-handoff.md` with: what was built, what the tests prove, key decisions made, known issues, exact commands to run next. Load this at the start of Phase N+1's first session. [^9]

### If/when running parallel work

**8. Git worktrees for independent pipeline stages.** The scraper, KG build, and training pair generation are largely independent after Phase 1 data is collected. Each can run in its own worktree with a dedicated Claude session. This matches Boris Cherny's stated top productivity unlock. [^4]

**9. Subagent for codebase investigations.** When you need to understand how a part of the codebase fits together before implementing, use: *"Use a subagent to investigate how the knowledge graph assembly connects to the training pair generator and report back a summary."* Keeps the main context clean for implementation decisions. [^1]

### What to avoid continuing

- Running long sessions that span multiple phases
- Updating `CLAUDE.md` with session state or temporary decisions — that's what `claude-progress.txt` is for
- Relying on `--continue` for cross-phase work without a handoff file — the session history is not a substitute for structured state

---

## Data Tables

### Tool Selection Matrix for This Project

| Scenario | Recommended approach | Rationale |
|---|---|---|
| Daily task execution (single task) | Fresh session + `claude-progress.txt` | Lowest overhead; matches Boris Cherny's actual practice |
| Phase-level task board (60 tasks) | Task Master AI or CCPM | Structured JSON/Issues avoids markdown drift; dependency tracking |
| Parallel independent stages | Git worktrees + separate sessions | Anthropic's stated top unlock; avoids file conflicts |
| Cross-session context | `claude-progress.txt` + `context/plans/phase-N-handoff.md` | Direct application of Anthropic harness pattern |
| Codebase investigation | Subagent delegation | Keeps main context for reasoning, not bulk file reads |
| Stable architectural decisions | ADRs in `context/decisions/` | Context compression; already partly done in this repo |
| Inner-loop repetitive tasks | Slash commands in `.claude/commands/` | Boris Cherny's stated practice; reduces prompt repetition |

---

## Gaps & Caveats

- Boris Cherny's workflow details come primarily from social media posts and third-party summaries, not a formal engineering blog post. The core claims (worktrees, slash commands, CLAUDE.md at 2,500 tokens) appear consistent across multiple independent sources but were not directly verified against a primary URL.
- The 56% skill invocation failure rate comes from a single community evaluation — not an Anthropic official benchmark. Treat as directionally correct, not authoritative.
- The ETH Zürich CLAUDE.md research result (LLM-generated files reduce success by ~3%) comes from search result summaries and was not verified against the primary paper.
- No strong public signal exists for the optimal task granularity for a project like this one (60 tasks / 6 phases / solo). The Anthropic harness papers target fully autonomous multi-hour runs; Boris Cherny's workflow targets parallel feature development on an existing codebase. Solo multi-phase greenfield projects are underrepresented in published guidance.
- Anthropic's Agent Teams feature (shipped Feb 2026) is experimental and disabled by default. Do not build around it for production work yet.
- Task Master AI's dual source-of-truth risk (JSON vs. generated markdown) is noted but the severity depends heavily on whether you edit the markdown files directly. If you treat the markdown as read-only views, the risk is low.

---

## Sources

[^1]: [Best Practices for Claude Code](https://code.claude.com/docs/en/best-practices) — accessed 2026-04-12
[^2]: [Create custom subagents — Claude Code Docs](https://code.claude.com/docs/en/sub-agents) — accessed 2026-04-12
[^3]: [How Boris Uses Claude Code](https://howborisusesclaudecode.com) — accessed 2026-04-12
[^4]: [Boris Cherny on X / Threads — slash commands, worktrees](https://x.com/bcherny/status/2007179847949500714) — accessed 2026-04-12
[^5]: [Building a C compiler with a team of parallel Claudes — Anthropic Engineering](https://www.anthropic.com/engineering/building-c-compiler) — accessed 2026-04-12
[^6]: [Effective harnesses for long-running agents — Anthropic Engineering](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) — published 2025-11-26
[^7]: [Harness design for long-running application development — Anthropic Engineering](https://www.anthropic.com/engineering/harness-design-long-running-apps) — published 2026-03
[^8]: [gsd-build/get-shit-done — GitHub](https://github.com/gsd-build/get-shit-done) — accessed 2026-04-12
[^9]: [parcadei/Continuous-Claude-v3 — GitHub](https://github.com/parcadei/Continuous-Claude-v3) — accessed 2026-04-12
[^10]: [automazeio/ccpm — GitHub](https://github.com/automazeio/ccpm) — accessed 2026-04-12
[^11]: [eyaltoledano/claude-task-master — GitHub](https://github.com/eyaltoledano/claude-task-master) — accessed 2026-04-12
[^12]: [AI Token Management: Why Your Claude Code Session Drains Faster Than It Should — MindStudio](https://www.mindstudio.ai/blog/ai-token-management-claude-code-session-drains) — accessed 2026-04-12
[^13]: [shihchengwei-lab/claude-code-session-kit — GitHub](https://github.com/shihchengwei-lab/claude-code-session-kit) — accessed 2026-04-12
[^14]: [Cline v3.25: The Coding Agent Built for Hard Problems](https://cline.ghost.io/cline-v3-25/) — accessed 2026-04-12
[^15]: [smtg-ai/claude-squad — GitHub](https://github.com/smtg-ai/claude-squad) — accessed 2026-04-12
[^16]: [Claude Code Memory System Explained — Milvus Blog](https://milvus.io/blog/claude-code-memory-memsearch.md) — accessed 2026-04-12
[^17]: [MrLesk/Backlog.md — GitHub](https://github.com/MrLesk/Backlog.md) — accessed 2026-04-12
[^18]: [Roo Code vs Claude Code (2026) — Morph](https://www.morphllm.com/comparisons/roo-code-vs-claude-code) — accessed 2026-04-12
[^19]: [Orchestrate teams of Claude Code sessions — Claude Code Docs](https://code.claude.com/docs/en/agent-teams) — accessed 2026-04-12
[^20]: [The ADR Pattern for Claude — 7tonshark](https://7tonshark.com/posts/claude-adr-pattern/) — accessed 2026-04-12

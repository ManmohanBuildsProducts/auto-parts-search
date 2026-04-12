# Session State

**Rolling dashboard. Open this first.** One page, always current. Claude updates via `/wrap` at session end.

Last updated: 2026-04-12 (Phase 2b execution complete — PDFs, golden-v1, determinism, notebook skeleton)

---

## 🟢 Current focus

Phase 2b mechanically complete except LLM ITI re-extraction. Next sprint = T506a-real (deliver first audit to a live prospect) + T102b/T103b (ITI re-extract). Everything else in the repo is now honest, reproducible, and shippable.

## ✅ Done (recent — last 2 sessions)

- **183/183 tests passing** — full suite green, no xfails needed.
- **Phase 2b execution batch (commit 775e446):**
  - T113-verify: `build-graph-db` ran end-to-end against real data — 2,627 nodes, 3,375 edges, 3.3MB graph.db.
  - T101b: 6 DGT ITI PDFs downloaded + committed (~8.7MB).
  - Parser audit: HSN/ASDC/NHTSA confirmed clean (real scraping, output-to-source ratio >100x). Only ITI has hand-curation.
  - T603a upgrade: per-function `rng = Random(seed)` pattern in `catalog_pairs.py`.
  - T603-verify: 2 consecutive runs byte-identical — determinism claim closed.
  - T603e: `data/training/golden/` promoted to golden-v1 with SHA256s in METADATA.md.
  - T102c: provenance disclosure added to decisions/003 + PRODUCT.md moat claims honestly framed.
  - T506a: `notebooks/search_audit.ipynb` skeleton — OpenAI embeddings + zero-result rescue + revenue-leak estimate + markdown report.
- **Session dashboard + global install (earlier in session):**
  - `SESSION_STATE.md`, `/start` `/status` `/wrap` commands globally at `~/.claude/commands/`.
  - SessionStart hook globally at `~/.claude/hooks/session-state.sh` (smoke-tested).
  - `~/.claude/rules/session-hygiene.md` makes the scaffold auto-bootstrap in every future project.
  - `architecture` skill, CLAUDE.md trimmed to <100 lines.
- **Phase 2b scaffolding (earlier):**
  - ADRs 005–011, plans, TASKS.md reconciled, memory/regressions.md, market + workflow research reports, session retrospective.
  - SQLite KG (graph_db.py + 7 passing tests + CLI).
  - Cline Kanban deleted.

## 🟡 In progress / partial

- **Golden-v1 is partial-perfect** — deterministic + hashed, but upstream raw-data snapshot (T603b/c Backblaze URL + SHA) is still TBD. Bit-identical re-run from cold clone blocked only on the B2 upload.

## 🔴 Blocked / pending external action

- **T603c Backblaze B2 upload** — needs user credentials.
- **Cline VS Code extension disable** — user-machine action; JSON is gone from repo.
- **T706 live-verify SessionStart hook** — open a fresh Claude Code session in this repo; hook script smoke-tested green but not yet observed firing in a real session.
- **T505 real prospect list** — user to name 5 target mid-market Indian platforms.

## 🔷 Next up (ranked by leverage)

1. **T506 — deliver first free audit** — use `notebooks/search_audit.ipynb` against a real prospect's catalog+queries. Single highest-EV item. ~4 hr per audit including prep.
2. **T102b/T103b — LLM re-extract ITI content from PDFs** — 6 LLM passes, merge into existing hand-curated set with provenance fields. Rebalances toward 2W/3W. ~2–3 hr.
3. **T208 — split benchmark into dev/test** — deterministic seed. ~15 min. Unblocks Phase 3 training loop.
4. **T603b/c — MANIFEST + B2 upload** — completes the reproducibility chain. ~30 min once B2 account exists.
5. **T208b — expand benchmark ground-truth top-20 graded labels** — via LLM judge. ~1 hr. Unblocks nDCG@10 measurement.
6. **T112 — Boodmo → HSN category mapping for top 1K parts** — enriches KG for Phase 3 pair generation. ~2 hr.
7. **Phase 3 T303a — `training/evaluate.py` harness** — pairs with T208. ~30 min.

## 🗝 Key recent decisions

- **Stay vertical (auto parts), reposition as Indian multilingual commerce** — ADR 011.
- **Collapse Phase 3 + 4 into a training loop** — unit of work is the `(pair_strategy, model, benchmark)` triple — ADR 006.
- **SQLite for KG** — JSON = committed inputs, `.db` = derived — ADR 007.
- **ITI v1 is hand-curated** — disclosed in PRODUCT.md + decisions/003 addendum — ADR 008.
- **Session-hygiene is a global rule** — `~/.claude/rules/session-hygiene.md` — Claude auto-maintains this scaffold without prompting.
- **Golden-v1 promoted** — `data/training/golden/` with SHA256s in METADATA.md — ADR 009.

## 🚨 Watch-outs (surface every session)

- "Done" ≠ "artifact exists." Done = verified outcome (`memory/regressions.md`).
- Do NOT generate training pairs without a model to consume them (ADR 006; T200-T206 post-mortem).
- `TASKS.md` is the single task-board source. Never introduce a parallel tool-state board.
- CLAUDE.md stays <100 lines / 2,500 tokens. Architecture → skills. Decisions → ADRs.
- Experiments live in `data/training/experiments/<date>-<hypothesis>/` — never mutate `golden/` directly. Promotion is a deliberate commit.

---

## How to use this file

- **You (passenger) opening project:** read this. 30 seconds. You know where we are.
- **Claude starting a session:** auto-injected via `~/.claude/hooks/session-state.sh`. Also `/status`.
- **Claude ending a session:** `/wrap` — updates this file + proposes commits.
- **If stale:** `/status` to refresh from git log + TASKS.md.

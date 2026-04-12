# Session 2026-04-12 — Learnings

Audit + cleanup + strategic review session. Solo founder + Claude (Opus 4.6, 1M context).

---

## Domain / project learnings

### L1 — "Parsed from DGT syllabi" was actually "hand-curated from founder's reading"

The `iti_systems.json` (124 parts) and `iti_diagnostics.json` (103 chains) are **~95% hardcoded Python dicts**, not PDF-extracted.

Evidence:
- `scrapers/iti_systems_parser.py:35–277` — `VEHICLE_SYSTEMS` is a hand-written list.
- `scrapers/iti_scraper.py:280–1635` — `STRUCTURED_DIAGNOSTICS` is 1,355 lines of hand-written dict entries with decorative `source_page: 0`.
- `.gitignore:10` excludes `*.pdf`; PDFs were never committed. Fresh clone → parser runs on zero PDFs → identical output (proving 100% hardcoded).
- Pre-existing test `tests/test_iti_scraper.py::test_minimum_100_chains` silently validates the hardcoded count (98 from dict, expects ≥100 with PDF contribution that never happens on CI).

Implication: claim "extracted from DGT ITI syllabi" in commits + decisions/003 is a truth-in-labeling problem. Content quality is fine; provenance claim isn't. Captured in ADR 008.

### L2 — Phase 3 open-loop failed; collapse pair-gen + model into one loop

T200/T201/T202/T206 (HSN hierarchy, ITI systems, diagnostic chains, merge) were all executed to completion 2026-04-09 → 2026-04-10 and then trashed 2026-04-11. Root cause: no model in the loop. "Done" = a `.jsonl` exists. Without training, you can't measure whether graded-label schema or pair mix is good. ADR 006 collapses Phase 3 + 4 into a single training loop; unit of work is the triple `(pair_strategy, model_checkpoint, benchmark_score)`.

### L3 — 4W bias in the KG matches founder's familiarity, not market reality

Current 103 chains split: LMV/HMV 66 (64%), 2W 12 (12%), tractor 12, EV 11, 3W 1, stationary 1.
`memory/learnings.md:13` says 2W is the volume play (260M vehicles). The hand-curation inherited the founder's 4W model. Real LLM extraction from the Mechanic Two & Three Wheeler PDF (1.6MB, ~150pp) will rebalance.

### L4 — Algolia has zero public Hindi NLP

Market research (2026-04-12) confirmed: Algolia NeuralSearch doc mentions 17 supported languages; Hindi is not one. Only Indic-language forum thread is from 2018, pre-NeuralSearch. No Indian commerce customer is named anywhere. This is the clearest unexploited gap in the category.

### L5 — Klevu's #1 complaint is cost, not retrieval quality

Across G2, TrustRadius, Capterra, the top low-star theme is pricing opacity, not search relevance failures. Validates the "cheaper domain-specific alternative" wedge at Rs.8–25K/mo where Klevu's $499+ floor is unreachable.

### L6 — Sajari + Klevu already consolidated; no exit path to Algolia acquisition for this thesis

Sajari → Algolia (2021). Klevu + Searchspring → Athos Commerce via PSG (Jan 2025). The acquirers buy customer bases and Western NLP, not Indian-language models. This project does not have a clear acquisition path; must be built to standalone cash flow.

### L7 — ONDC is latent distribution

10M+ txns/month, open Beckn `/search` protocol, no semantic/Hindi layer. A query-intelligence service that speaks Beckn could insert itself across every buyer app. Too early to build for; tracked as optionality in ADR 011.

---

## Process learnings

### P1 — Dual sources of truth always drift

`context/TASKS.md` (markdown) + `context/cline-kanban-board.json` (Cline) drifted by 7+ completed tasks + 4 trashed ones within one work week. No reconciliation step existed. Fix: single-source markdown (ADR 005). Tool state becomes a *derived* view, never authoritative.

### P2 — "Done" must equal "verified outcome," not "artifact exists"

All three incidents in `memory/regressions.md` share the pattern: work moved to done because a file/card existed, not because a number was measured. Principle going forward: if you can't point to a benchmark score, commit hash, or provenance trail, it's work-in-progress.

### P3 — Open-loop execution burns weeks

T200-T206 produced real artifacts (1,300-line `hsn_hierarchy_pairs.jsonl`, full parser, tests) that were discarded. The diff between "1 week of open-loop pair-gen" and "1 week of closed-loop pair-gen + tiny model" is a discarded PR vs a measurable signal. Never generate training data without a model consuming it.

### P4 — Market research should precede positioning decisions, not follow them

The "stay vertical vs horizontal" decision was almost made on founder intuition ("auto parts is my thing" vs "horizontal is bigger TAM"). A 30-minute research-agent call surfaced: Algolia has no Hindi, Klevu's complaint is cost, ONDC is open. These are the decision-relevant facts. Cost of the research: 30 min agent time. Value: the entire ADR 011 rests on it.

### P5 — Research-agent for any decision that depends on market state

Generalization of P4. Any claim of the form "no one else is doing X" or "market is saturated" or "this vendor charges Y" should be verified via a research agent before becoming a decision input. Knowledge-cutoff drift makes founder-memory unreliable.

### P6 — Unit tests on a real-shape fixture beat unit tests on an idealized fixture

`tests/test_graph_db.py` uses a hand-built graph dict whose shape mirrors what `build_knowledge_graph()` actually returns (verified via grep of `node_type`, `provenance.source`, `source_id`/`target_id` keys). Tests passed first try (after FTS fix). Without shape-matching, the tests would have passed against a fictional API.

### P7 — FTS5 `content=''` is a footgun

Contentless mode doesn't store the indexed columns — reading back `id` returns NULL. Default FTS5 (no `content=` clause) is correct for our size. Caught in unit tests before shipping; logged here so future-self doesn't rediscover.

### P8 — Session structure that worked this session

Pattern that compressed well:
1. First turn: audit-only, no edits. Output = punch list.
2. Middle turns: Q&A on the punch list; user approves/modifies items.
3. Last turn: batched write of all approved items in parallel tool calls.

The batched-write turn hit ~15-20 file creates + edits in a single pass. This is the "plan then execute" cycle — keep planning turns lean (no code yet), keep execution turns batched (no deliberation yet).

---

## Tool / workflow learnings

### T1 — Parallel tool-call batching matters
When writing 7 ADRs + 2 plans + 5 code files, batching them in one message was dramatically faster than sequential. Each sequential round-trip costs latency + can re-trigger hooks.

### T2 — Background research agents while main-thread does work
Dispatched the market-research agent at the start of a turn and wrote ADRs in parallel. The agent reported back mid-next-turn. Net: 30 minutes of research happened alongside the work, not serially.

### T3 — The 1M context window is generous but not infinite
The PROJECT_LOG.md file alone was 820KB / 17K lines. Loading it naïvely would have consumed ~half the window. Grep-sampling + targeted Read ranges preserved context for actual work.

### T4 — `<system-reminder>` about task tools repeats under latency
The "task tools haven't been used recently" reminder fired 4+ times during this session. It's noisy; ignoring it is correct when the work is genuinely ADRs + plans + code edits that don't need TaskCreate.

### T5 — `git rm` works inline; don't ask Bash permission for it each time
User approved the kanban deletion once; `git rm` succeeded without further prompt. Same pattern for other staged deletions.

# Regressions & Incidents

Things that went wrong, why, and how to avoid repeating them.

---

## 2026-04-11: Phase 3 pair-generation open-loop (T200/T201/T202/T206 trashed)

**What happened.** Between 2026-04-09 and 2026-04-11, Phase 3 tasks T200 (HSN hierarchy pairs), T201 (ITI system pairs), T202 (diagnostic chain pairs), and T206 (merge all to `all_pairs_v2.jsonl`) were executed end-to-end. Output files were generated (PROJECT_LOG:7841 shows `hsn_hierarchy_pairs.jsonl` at 1,300 lines + a parser + tests committed in that branch). All four tasks were then trashed in Cline Kanban on 2026-04-11.

**Why it failed.** Open-loop execution. No model was trained on the output to validate whether the chosen pair-generation strategy improved or hurt benchmark scores. The "done" criterion — "graded similarity pairs: siblings=0.85, cousins=0.4, distant=0.2" — was a schema claim, not an outcome claim. Without a model in the loop, the judgment "is this pair set good?" cannot be made.

**How to avoid.** ADR 006 collapses Phase 3 (pair gen) + Phase 4 (model) into a single training loop. The atomic unit is the triple `(pair_gen_strategy, model_checkpoint, benchmark_score)`. No pair-generation variant is declared done until a model has been trained on it and benchmarked. Experiments live under `data/training/experiments/<date>-<hypothesis>/`; only promoted results touch `data/training/golden/`.

**What to reuse.** The trashed code likely contains valid work (graph-distance calculation, graded-label scaffolding). Before starting T200b/T201b/T202b, check the reflog or the trashed kanban entries for salvageable code.

---

## 2026-04-09 (discovered 2026-04-12): TASKS.md / Cline Kanban drift

**What happened.** Two authoritative task boards running in parallel (`context/TASKS.md` and `context/cline-kanban-board.json`). Phase 2 tasks T100–T111 were completed (commits 4cae4c1, 0694bc1, 53e32e9, 34e5968, 7ce13be, 7f51fa9, 95063dc, 064e161, 3d1bb09) but TASKS.md still listed them under "Backlog" on 2026-04-12.

**Why it failed.** Dual sources of truth. Cline updates its JSON on task-state changes; TASKS.md required manual update and didn't get one. No reconciliation step.

**How to avoid.** ADR 005: TASKS.md is the single source. Cline's JSON is deleted. Manual update to TASKS.md is the mandatory post-session step.

---

## 2026-04-12: ITI provenance overclaim (discovered audit, not incident yet)

**What happened.** Commit message "Add ITI syllabus parser for diagnostic chains (Phase 2, T103)" and decisions/003 ("DGT ITI syllabi are the richest single source") imply that the 103 diagnostic chains and 124 parts in `iti_*.json` were extracted from PDFs. Audit on 2026-04-12 found they are ~95% hand-curated in Python (`scrapers/iti_scraper.py:280–1635` is `STRUCTURED_DIAGNOSTICS` as a hardcoded dict; `scrapers/iti_systems_parser.py:35–277` is `VEHICLE_SYSTEMS` as a hardcoded list). PDFs are `*.pdf`-gitignored and never committed, so the parser runs on zero PDFs on a fresh clone and produces the same output — proving 100% hand-curation.

**Why it matters.** Not yet an incident. Becomes one the first time a prospect/investor asks "show me how you extracted this from DGT syllabi." The answer "I hand-curated it based on my reading" is fine and honest; "extracted by the parser" as commits imply is not defensible.

**How to avoid.** ADR 008 (disclosure + re-extraction plan). T101b commits the PDFs; T102b/T103b re-extract via LLM with per-entry provenance. Public framing updated: v1 is hand-curated; v2 is LLM-extracted.

---

## Pattern to watch: claiming "done" without outcome evidence

All three incidents above share a structure: the builder moved work to "done" based on an artifact existing (a pair file, a kanban card, a JSON file) rather than an outcome being measured (a benchmark score, a reconciled git state, a traceable provenance). Principle going forward:

> **Done is not an artifact. Done is a verified outcome.**

If you can't point to a number, a commit hash, or a provenance trail, it's not done — it's a work-in-progress that someone forgot to finish.

---

## 2026-04-22: T610 / CADeT execution — four engineering-discipline regressions (caught by codex handoff)

During the CADeT listwise training plan execution (commits `0faed40` → `4c4d083`), four operational mistakes burned roughly a full session of cleanup before training could even be attempted. Codex picked up the handoff (session `019db5a2-9de0-7b01-8ade-e7e6cba1dcf8`) and had to repair the environment before it could resume work. All four are repeatable patterns and deserve named rules.

### Regression A — blind `pip install -U` of a shared ML-library dep

**What happened.** To check whether `huggingface-cli jobs` was available, ran `pip install -U "huggingface_hub[cli]"`. Global site-packages upgraded to `huggingface_hub==1.11.0`, which is incompatible with the installed `transformers==4.48.3` (needs `huggingface_hub<1.0`). Every test that imported `transformers` (a lot of them) started failing at import time. Codex had to diagnose and downgrade before any training work could continue.

**Why it matters.** The ML ecosystem (`huggingface_hub`, `transformers`, `sentence-transformers`, `datasets`, `torch`) has monthly breaking upgrades across library boundaries. A global upgrade of any one silently breaks the others.

**How to avoid.**
1. Pin all four libraries in `requirements.txt` at project bootstrap, not after breakage. Upper bound on major version (`<1.0.0`, `<5.0.0`), lower bound on required features.
2. Probe new features in a throwaway venv (`uv run --with pkg==X`) or use `pip install --dry-run` first.
3. Never run `pip install -U` on a shared ML dep mid-task just to check something.

### Regression B — heavy imports at module top level break tests

**What happened.** `scripts/generate_listwise_data.py` had `from transformers import AutoModelForSequenceClassification, AutoTokenizer` and `import torch` at module scope. Two effects:
1. Unit tests that only exercised lightweight helpers (`build_query_prompt`, `parse_query_response`) still paid the transformers import cost.
2. When `transformers` import broke (see Regression A), those same unit tests crashed at collection time instead of running cleanly.

**How to avoid.** At module top, only import: stdlib, types used in signatures, and things needed on every call path. Heavy ML deps (`transformers`, `torch`, `sentence_transformers`) go inside the function that actually uses them. Use `if TYPE_CHECKING:` for type-only imports.

```python
# wrong — heavy import at top
from transformers import AutoTokenizer
def score(...): ...

# right — lazy inside the function
def score(...):
    from transformers import AutoTokenizer
    ...
```

### Regression C — script works as `-m` but not as direct execution

**What happened.** `training/train_listwise.py` had `from training.listwise_loss import ListwiseKLLoss`. The plan's smoke-test step said `python training/train_listwise.py --smoke-test`, which fails with `ModuleNotFoundError: No module named 'training'` because the `training/` parent isn't on `sys.path` for direct execution. Only `python -m training.train_listwise` works.

**How to avoid.** For any script with intra-repo imports that will be invoked directly:

```python
try:
    from training.listwise_loss import ListwiseKLLoss
except ModuleNotFoundError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from training.listwise_loss import ListwiseKLLoss
```

Or enforce `python -m ...` consistently in every plan, command, and README — but the path shim is safer because users copy-paste from anywhere.

### Regression D — `model.encode()` returns no-grad tensors; can't train on its output

**What happened.** Smoke test crashed with `RuntimeError: element 0 of tensors does not require grad and does not have a grad_fn`. Root cause: `sentence_transformers.SentenceTransformer.encode()` runs under `torch.no_grad()` internally for inference speed. Calling it inside a training loop gives you a dead-end tensor — `loss.backward()` fails because the graph has no grad edges.

**How to avoid.** When fine-tuning a SentenceTransformer, never use `model.encode()` in the training step. Use the forward pass directly:

```python
def encode_with_grad(model, texts, device):
    features = model.tokenize(texts)
    features = {k: v.to(device) for k, v in features.items()}
    out = model(features)
    return F.normalize(out["sentence_embedding"], p=2, dim=-1)
```

Alternative: `encode(..., convert_to_tensor=True)` is also `no_grad` — don't be fooled by the "tensor" return type. Only `model(features)` preserves grads.

### Meta-pattern across A–D

All four are *environmental/plumbing* errors, not ML-modeling errors. Each cost ~15–30 minutes to diagnose. They share a pattern: **a known-good reference implementation (the plan, the unit test, the paper recipe) was copied without verifying the runtime context matches**. The fix for each is explicit: pin environments, lazy-import heavy deps, add path shims, read the library's internals before assuming a function is gradient-safe. These belong in every new ML-engineering plan's pre-flight checklist.

# Decision 012: Phase 3 compute — Colab Free + Hugging Face Hub, $0 v1

**Date**: 2026-04-13
**Status**: Decided

## Context
Phase 3 (training loop) needs GPU compute — fine-tuning an embedding model on 20K+ pairs is the only step in the project that a MacBook can't do well. Solo-founder, pre-revenue: total v1 budget = ~$0–50.

## Decision
Run Phase 3 across four "rooms," each pinned to a specific service:

| Step | Where | Service | Cost | Why |
|------|-------|---------|------|-----|
| 1. Generate training pairs | Local | Laptop (Mac) | $0 | Pure Python over `graph.db`; no GPU needed |
| 2. Fine-tune model | Cloud GPU | **Google Colab Free** (T4) | $0 | Free Nvidia T4 (16GB VRAM), 12-hr sessions; sufficient for sentence-transformers fine-tuning at our scale |
| 3. Store trained model | Cloud | **Hugging Face Hub** (private) | $0 | Already have account `ManmohanBuildsProducts`; same auth flow as raw-data dataset |
| 4. Evaluate (run 195-query benchmark) | Local | Laptop (Mac) | $0 | Pulls model from HF; CPU inference is fine for 195 queries |

**Total expected v1 cost: $0.**

## Fallback ladder (when Colab Free hits limits)

Move up only when needed; never default to a paid tier first.

| Trigger | Upgrade to | Cost |
|---------|-----------|------|
| Colab Free disconnects mid-epoch (12hr cap, idle timeout) | Colab Pro | $10/mo |
| Need an A100 for a specific experiment (e.g. larger batch size, full-precision) | Modal or RunPod | $1–2/hr pay-per-second |
| Want a hosted demo URL (post first model) | HF Spaces (CPU free / GPU $9+/mo) | $0–9/mo |
| Eventual production inference at customer scale | Decide at Phase 5 (T401 FastAPI). Likely Modal or self-hosted on a $20-40/mo VPS w/ ONNX-quantized model on CPU | TBD |

## Why this stack (vs alternatives we ruled out)

- **AWS / GCP / Azure** — overkill, painful credit-card setup for ~$5 of actual compute.
- **Mac MPS (PyTorch on Apple Silicon)** — works but ~3–5× slower than a T4; 16GB unified memory is borderline; risk of OOM on larger models. OK for sanity-check runs, not the primary path.
- **Replicate / Lambda Labs / Vast.ai** — fine but extra vendor onboarding for marginal benefit over Colab + Modal.
- **Train from scratch** — never. We fine-tune an existing pre-trained base (BGE-m3, Jina v3, multilingual-e5, OpenAI/Cohere via API for benchmarking).

## What gets committed where

- **Code** (training script, evaluation script, Colab notebook): in this repo at `notebooks/train_v1.ipynb` and `training/evaluate.py`.
- **Trained model artifacts**: pushed to private HF repo `ManmohanBuildsProducts/auto-parts-search-v1` (and v2, v3 ...).
- **Benchmark scores**: written to `data/training/golden/METADATA.md` "Models trained on this set" table after every promoted run.
- **Experiment artifacts** (failed runs, hyperparameter sweeps): `data/training/experiments/<date>-<hypothesis>/` (gitignored per ADR 009).

## User's role per training run

1. Open the Colab notebook in browser.
2. Paste HF token.
3. Click **Run all**.
4. Walk away ~30–60 min.
5. Come back to a printed scorecard + the model already pushed to HF.

No infrastructure setup, no AWS account, no credit card for v1 attempts. Everything reproducible from a fresh clone given the HF token.

## Linked ADRs

- ADR 006 (Phase 3 collapsed training loop) — the WHAT
- ADR 009 (reproducibility — manifest + seed + golden) — the upstream data
- ADR 010 (search tokenizer pipeline) — query-time, separate from this training step
- ADR 011 (positioning, GTM) — model performance unblocks first paid pilot

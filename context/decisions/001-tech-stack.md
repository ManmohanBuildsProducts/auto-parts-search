# Decision 001: Tech Stack

**Date**: 2026-04-08
**Status**: Decided

## Context
Choosing the stack for the training pipeline and eventual search API.

## Decision
- **Python** for all data pipeline, ML training, and API code
- **sentence-transformers** or **Jina v3** for embedding model (LoRA adapters for domain fine-tuning)
- **Qdrant** for vector DB (open-source, self-hostable)
- **FastAPI** for search API
- **Playwright** for JS-rendered site scraping
- **JSONL** for all intermediate data (products, training pairs)

## Rationale
- Python is the natural choice for ML/data pipeline work
- Jina v3 offers LoRA adapters — fine-tune without retraining the whole model
- Qdrant is purpose-built for search, no vendor lock-in
- JSONL is streamable and easy to inspect

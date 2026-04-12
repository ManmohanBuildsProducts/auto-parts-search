# Decision 010: Search tokenizer pipeline for Hindi/Hinglish/Devanagari

**Date**: 2026-04-12
**Status**: Decided (pipeline design; implementation is T402a)

## Context
Mixed-script queries ("brake ki patti", "engine garam", "ब्रेक पैड") will break every off-the-shelf BM25 tokenizer. Elasticsearch's `standard` analyzer, Typesense's default, Meilisearch's default — all treat Devanagari either as character n-grams (over-matches) or split badly on mixed-script boundaries. A custom-built tokenizer is unnecessary; the open Indic NLP stack is already good.

Separate from this: Sarvam AI's open-source tokenizer is a *BPE subword tokenizer for LLM generation*, not a search tokenizer. Different job. Not used here.

## Decision
Indexing and query-time pipeline:
```
raw text
  → IndicNLP normalize (Unicode canonicalization; handles nukta variants)
  → script detection (Devanagari / Latin / mixed)
  → if Devanagari: IndicTrans2 transliterate to Latin (dual-index in both scripts)
  → tokenize on whitespace + punctuation (IndicNLP tokenizer)
  → lowercase
  → domain lemma map (~300 hand-curated entries for auto-parts inflections where the stemmer fails)
  → IndicNLP Hindi stemmer OR Snowball English stemmer per language tag
  → BM25 index
```

## Components
- **AI4Bharat `indic-nlp-library`** (open source) — normalizer, tokenizer, Hindi stemmer.
- **AI4Bharat `IndicTrans2`** — Latin↔Devanagari transliteration for dual-indexing.
- **Domain lemma map** (new, ~300 entries) — auto-parts-specific inflections where stemming misses. Stored at `auto_parts_search/lemma_map.py`.
- **Snowball** for English content.

## Search engine choice: Meilisearch over Typesense
Reasons:
- Better out-of-box Unicode handling.
- Config-driven synonyms and stop-words, no custom plugin needed.
- Self-hostable + managed cloud both available.
- Lower infra cost than Elasticsearch for our scale.

## Scope of this decision
This ADR fixes the *pipeline architecture*. Implementation is task T402a (`context/plans/phase5-search-api.md` — not yet written). The lemma map will be curated during T402a from error analysis against the benchmark.

## Open question (deferred)
Whether to pre-translate Devanagari queries to Latin-script canonical form before embedding (reduces vector-space fragmentation) or embed both and ensemble. Decide during T303b base-model shootout.

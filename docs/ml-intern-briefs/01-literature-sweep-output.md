# ml-intern Literature Sweep Output
Generated: 2026-04-22, Claude Opus 4.6 via ml-agent-explorers web UI

---

## Technique 1: Cross-Encoder Listwise Distillation with Diverse Synthetic Queries (CADeT-style)
**Priority: #1 — Highest expected gain, directly addresses saturation problem**

| Attribute | Details |
|---|---|
| Problem it solves | 27K KG pairs + MNRL have saturated. Standard contrastive fine-tuning degrades pre-trained embedders. This injects domain-specific ranking knowledge via a teacher. |
| Key citations | Tamber et al., "Conventional Contrastive Learning Often Falls Short: Improving Dense Retrieval with Cross-Encoder Listwise Distillation and Synthetic Data", arxiv:2505.19274; Tamber et al., "Teaching Dense Retrieval Models to Specialize with Listwise Distillation and LLM Data Augmentation", arxiv:2502.19712 |
| Training data format | Listwise tuples: (query, [doc+, doc-_1, ..., doc-_K], [teacher_score_0, ..., teacher_score_K]) where teacher scores are min-max normalized cross-encoder logits. Query types: (1) Hindi natural, (2) Hinglish natural, (3) Romanized Devanagari, (4) English technical, (5) symptom/description, (6) brand+generic variant |
| Data generation recipe | Sample 50-100K passages from 26K-doc corpus. Generate 6 query types per passage via Llama-3.1-8B or Claude. Filter: retriever must return gold doc in top-20 AND cross-encoder teacher must rank gold doc #1. Yields ~30-50K training queries. |
| Loss | L = λ₁ * L_listwise (KL against teacher rankings) + λ₂ * L_InfoNCE, λ₁=0.6, λ₂=0.4 |
| Teacher | RankT5-3B or bge-reranker-v2-m3. Claude allowed for query generation/filtering. |
| Hardware / time | A100 80GB: synthetic gen ~1h (vLLM), teacher scoring ~2h, fine-tuning BGE-m3 ~1-2h. Total: 2-4h. |
| Estimated gain | Overall nDCG@10: +4 to +8 pts (0.430 → 0.470-0.510). Hindi/Hinglish: +6 to +12 pts. brand_as_generic: +3 to +6 pts. |

---

## Technique 2: CLEAR-style Cross-Lingual Alignment with Reversal + Transliteration Bridge
**Priority: #2 — Directly fixes Hindi/Hinglish -10 pt gap**

| Attribute | Details |
|---|---|
| Problem it solves | BGE-m3 has generic multilingual alignment but severe English bias in mixed-language pools. Hindi/Hinglish queries sit far from English catalog docs in embedding space. |
| Key citations | Hong et al., "Improving Semantic Proximity in IR through Cross-Lingual Alignment", arxiv:2604.05684; CLEAR, "Cross-Lingual Enhancement in Alignment via Reverse-training", arxiv:2604.05821; "How Transliterations Improve Crosslingual Alignment", arxiv:2409.17326 |
| Training data format | Triples: (q_en, p_en, p_hi) where p_hi = Hindi/Hinglish/Romanized translation of p_en. Reversed pairs: (p_en, q_hi+, q_hi-) using passage as anchor. Transliteration pairs: (q_devanagari, q_roman) as positives. |
| Data generation recipe | Take existing 27K English query-doc pairs. Translate queries to Hindi and Hinglish using NLLB-200-3.3B or Claude. Generate Romanized variants via Uroman/Indic transliteration. Mine 5 hard negatives per sample from top-30 to top-100 retrieved candidates. |
| Loss | L_CLEAR = λ₁·L_NCE(en-en) + λ₂·L_CL(reversed) + λ₃·L_KL(S_en ‖ S_hi) |
| Hardware / time | A100: translation ~30min, hard-negative mining ~20min, training ~1-1.5h. Total: ~2h. |
| Estimated gain | Hindi/Hinglish slice: +5 to +10 pts. English-English: -0.2 to +0.6 pts preserved. brand_as_generic: +2 to +4 pts indirect. |

---

## Technique 3: Entity-Aware Bi-Encoder with Brand/Generic/Part-Type Decomposition (EBRM-style)
**Priority: #3 — Specialized fix for brand_as_generic -15 pt gap**

| Attribute | Details |
|---|---|
| Problem it solves | Embedding model collapses brand and generic semantics into nearby vectors. Dense retrieval cannot disambiguate "Maruti" (brand intent) from "Maruti" (generic car reference). |
| Key citations | "Improving Text Matching in E-Commerce Search with EBRM", arxiv:2307.00370; "QueryNER: Segmentation of E-commerce Queries", arxiv:2405.09507; "Language Models are Surprisingly Fragile to Drug Names", arxiv:2406.12066 |
| Training data format | Entity-annotated pairs: (query, doc, entity_spans_query, entity_spans_doc, entity_types, relevance_label). Entity types: BRAND, GENERIC_TERM, PART_TYPE, MODEL, SYMPTOM. |
| Data generation recipe | Use HSN taxonomy + ITI diagnostic chains to construct entity-aware hard negatives. Use Claude to generate brand↔generic paraphrased queries. Augment with entity-dropped variants. |
| Architecture / loss | BGE-m3 backbone + entity-aware pooling. Final score = w_global * sim(query, doc) + Σ w_e * sim(query_entity_e, doc_entity_e). Train with entity-weighted InfoNCE (upweight brand/part-type contrasts 2-3×). |
| Hardware / time | A100: entity annotation ~30min, augmentation ~30min, fine-tuning ~1h. Total: ~2h. |
| Estimated gain | brand_as_generic: +8 to +15 pts. Hindi/Hinglish: +1 to +3 pts indirect. Overall: +3 to +6 pts. |
| Fusion note | Can combine with Technique 1: s_final = s_dense + α*s_entity |

---

## Recommended Execution Order

| Order | Technique | Rationale |
|---|---|---|
| 1st | Technique 1 (CADeT listwise distillation) | Biggest overall gain, fixes saturation, builds new training data |
| 2nd | Technique 2 (CLEAR cross-lingual alignment) | Stacks on #1; uses parallel data that #1 generates as side effect |
| 3rd | Technique 3 (EBRM entity-aware) | Specialized fix for brand_as_generic; can be fused with #1 at inference |

**Combined estimated gain if stacked:** nDCG@10 0.430 → 0.485-0.520, beating OpenAI's 0.468.
Hindi/Hinglish gap closed ~80%. Brand_as_generic gap closed ~60-80%.

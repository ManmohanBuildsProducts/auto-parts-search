# Phase 3b — γ / γ' Pair-Mining Spec

**Date:** 2026-04-15
**Status:** Draft (pending approval; no code yet)
**Target:** Close the catalog-side gap v3 has against OpenAI `text-embedding-3-large` on the 26K-doc round-2 dev set.
**Owner:** Solo (Manmohan)
**Supersedes / extends:** golden-v2 (`all_pairs_v2.jsonl`, 26,760 rows). γ/γ' pairs will live in `data/training/experiments/2026-04-15-gamma-catalog/` and, if the trained model beats the v3+BM25-tuned hybrid on dev, get promoted to `golden-v3`.

---

## 1. Why γ/γ'

Round-2 bench on the 26K corpus:

| Slice | v3+BM25-tuned hybrid | OpenAI text-emb-3-large | Gap |
|---|---|---|---|
| Overall nDCG@10 | 0.430 | 0.468 | **−0.038** |
| Hindi / Hinglish | — | — | **−0.10** |
| brand_as_generic | — | — | **−0.15** |
| part_number | — | — | **−0.09** |

The three losing slices are all **catalog-structure-aware** queries: they require the model to see an actual product name ("SparesHub 5-W30 Engine Oil") and resolve it to a generic term ("mobil" / "engine oil"), or see a 10-char alphanumeric PN and match it to a product name, or fuzz-match a vehicle name. Our current pair set is vocabulary-heavy; it has almost no structured "product name ↔ canonical query" supervision. That is the gap.

γ = first catalog-aware pair batch, trained as a v4-successor candidate.
γ' = expansion/cleanup batch that only happens if γ alone lands in the "almost gate" band (+3% to +5%). Spec for γ' is sketched at the end — full plan deferred until γ measures.

---

## 2. Inputs already in the tree

| Source | Path | Count | Notes |
|---|---|---|---|
| Meilisearch `parts` (catalog docs) | `127.0.0.1:7700/indexes/parts`, filter `doc_type = "catalog"` | **25,951** | Live index — authoritative corpus |
| ITI knowledge graph | `data/knowledge_graph/graph.db` (4,252 nodes / 5,445 edges) | — | Has part-type taxonomy + vehicle hierarchy |
| Vocabulary research | `training/vocabulary_pairs.py` | 1,593 (golden-v1) | Brand-as-generic seed list: Mobil, Bosch, NGK, Exide, Castrol, MRF, Dunlop, Delco, Servo, Bullet (22 brand-generic pairs in `BRAND_GENERIC_PAIRS_RAW`) |
| golden-v2 | `data/training/golden/all_pairs_v2.jsonl` | 26,760 | Current training set — retained as base |

### Catalog composition (sampled 100 docs × 5 offsets = ~500 docs; plus aggregate stats)

- **`spareshub`** — ~12–15K docs — 100% Skoda OEM part-number listings. Format: `"Skoda Genuine Parts - Part Number <PN> <SHORT_DESC>"`. `part_numbers` array populated. vehicle_make = Skoda. system = "Car Parts" (uninformative).
- **`bikespares`** — ~2–3K docs — mostly Bajaj fenders/mudguards, Royal Enfield, misc. Format: `"Front Fender / Front Mudguard Fit For Bajaj XCD 135Cc Black"`. No part_numbers. vehicle_make sometimes empty.
- **`eauto`** — ~10K docs — branded 2W parts. Brands: OES Handle Bar Switch, OES Front Fork Assembly, PRICOL, MK Auto Clutch Co., Spark Minda, Goetze, Dexo, Bajaj OE. vehicle_make populated (Hero, Bajaj, Suzuki, TVS, Yamaha, Honda, Royal Enfield). `system` field is the **part category** (Speedometer / Piston Cylinder Kit / Handle Bar Switch / Front Fork Assembly).
- **`carorbis`** — tail — detailing/accessories, mostly empty brand/make.

**Implication:** different sources have different strengths. SparesHub is pure PN→name. eauto is brand+make+system clean. bikespares is vehicle-compatible (same-part-across-trims). We mine each source the way it is structured.

---

## 3. Mining strategies

For each strategy below: data source, extraction rule, estimated pair count, label scheme (1.0 = synonym, 0.5 = related/weaker, 0.0 = negative — follows `all_pairs_v2.jsonl` scheme from ADR 013), and known risks.

### 3.1 Strategy A — Part-Number ⇄ Product-Name aliasing (SparesHub)

**Goal:** teach the model that "`5J5820045B`" and "Skoda Genuine Parts - Part Number 5J5820045B QWA CONTROLS" and "skoda controls 5J5820045B" are the same thing.

**Source:** SparesHub catalog docs where `part_numbers` is non-empty (≈ 13K rows estimate).

**Generation rules (per doc):**
1. `text_a = <part_number>` (raw, uppercase)  ↔  `text_b = <name>` → label **1.0** → `pair_type="part_number_alias"`
2. `text_a = <part_number>.lower()` ↔ `text_b = <name>` → label **1.0** (case-robustness)
3. `text_a = "<vehicle_make> <part_number>"` ↔ `text_b = <name>` → label **1.0**
4. `text_a = "<short_desc>"` (last 1–3 tokens of name, e.g. "OXYGEN SEN", "SUN VIZOR") ↔ `text_b = <name>` → label **0.5** (partial; descriptions are truncated)
5. **Negatives:** for each positive, sample 1 PN from a DIFFERENT vehicle_make → label **0.0**, `pair_type="part_number_neg"`.

**Estimated count:** 13K × (3 positives + 1 negative) ≈ **52K pairs**. ⚠️ TOO LARGE — dominates the set. **Cap:** sample 4,000 unique PNs (stratified by first 2 chars of PN to cover VW/Skoda PN families), then generate all 4 variants = **16K pairs** (12K positive + 4K negative). Further down-sample if needed to stay under 30% of total pairs.

**Risks:**
- PN aliasing is a near-lexical task; BGE-m3 may learn it trivially and overfit. Mitigate with graded labels + sampling diversity.
- SparesHub names are formulaic ("Skoda Genuine Parts - Part Number ..."). The model could learn the boilerplate rather than the alias. Mitigate by training on `text_b = _raw_description` stripped of the "Skoda Genuine Parts - Part Number X" prefix in 50% of variants.
- Skoda-heavy. Offsets against other brands — may shift relevance toward Skoda queries. **This is the biggest risk** and why γ must be benchmarked on the full round-2 dev, not a SparesHub subset.

### 3.2 Strategy B — Brand-as-generic, catalog-anchored (eauto + research seed)

**Goal:** teach "Bosch plug" → "spark plug for Hero Splendor"; "Mobil" → engine oil product; "PRICOL" → speedometer; "Goetze" → piston kit.

**Source:**
- Seed map from `vocabulary_pairs.py::BRAND_GENERIC_PAIRS_RAW` (22 pairs: mobil→engine oil, bosch→spark plug, NGK→spark plug, Castrol→engine oil, Exide→battery, Servo→brake booster, Delco→distributor, Dunlop/MRF→tyre, Bullet→Royal Enfield).
- eauto catalog brands that are themselves generic category markers (`OES <Category>` e.g. "OES Handle Bar Switch" → category = Handle Bar Switch; "OES Front Fork Assembly" → front fork; PRICOL → speedometer; Goetze → piston).

**Generation rules:**
1. For each (brand, generic_category) in seed: scan catalog for 5 real product names where `brand==B OR name contains B`. Then emit:
   - `text_a = <brand>` ↔ `text_b = <product_name>` → **1.0** → `pair_type="brand_catalog_positive"`
   - `text_a = <brand> <vehicle_make> <vehicle_model>` ↔ `text_b = <product_name>` → **1.0**
   - `text_a = <generic_category>` ↔ `text_b = <product_name>` → **1.0**
2. Cross-brand pair (positive symmetry): `text_a = "<brand> <vehicle>"` ↔ `text_b = "<generic> for <vehicle>"` → **1.0**
3. **Negatives:** `<brand>` ↔ `<product_name_from_different_category>` → **0.0**.

**Estimated count:** ~30 effective brand-generic pairs × 5 products × 3 variants = **~450 positives** + ~150 negatives = **~600 pairs**. Small but high-leverage — directly addresses the −15pt brand_as_generic gap.

**Risks:**
- Seed list is small (22 brand-generic mappings). The model may memorize rather than generalize. Mitigate by mining brand occurrences from the catalog (instead of hardcoding) — any brand that appears >30 times AND whose products cluster in one `system` category is a candidate for an auto-mined pair.
- "Bullet" overlap with the CV-joint boot / trunk ambiguity. Mitigate by prefixing with "motorcycle" or "Royal Enfield" in the text_b.

### 3.3 Strategy C — Vehicle-compatible parts (eauto + bikespares)

**Goal:** teach "Swift brake pad ≈ Maruti brake pad"; "Hero Splendor shocker ≈ Splendor shock absorber"; "Bajaj Pulsar fender ≈ Bajaj XCD fender (same category)".

**Source:** eauto catalog (clean `system`+`vehicle_make`+`vehicle_model`) and bikespares (vehicle encoded in name).

**Generation rules:**
1. **Same part-category + same vehicle make + different model** (synonymic within a 2W make):
   - Group by (system, vehicle_make). Within each group, sample 5 product pairs.
   - `text_a = <product_name_A>` ↔ `text_b = <product_name_B>` → **1.0** → `pair_type="vehicle_compatible_positive"`
   - Source-tag: `"group:eauto:<system>|<make>"`.
2. **Same part-category + different vehicle make** (related but not synonym):
   - `text_a = <product_name_A>` ↔ `text_b = <product_name_B>` → **0.5** → `pair_type="vehicle_cross_make"`
3. **Canonical-query form:** `text_a = "<vehicle_make> <vehicle_model> <system>"` ↔ `text_b = <product_name>` → **1.0**. Hinglish variants: also emit `text_a = "<make> ka <system-hindi>"` for the 5 most common systems (brake pad → brake ki patti, shock absorber → shocker, etc., reuse vocabulary seeds). → **1.0** → `pair_type="vehicle_compatible_hinglish"`.
4. **Negatives:** `text_a = <product_name_A (system=brake)>` ↔ `text_b = <product_name_B (system=speedometer)>` same vehicle → **0.0**.

**Estimated count:**
- eauto has ~20 distinct `system` values × ~8 makes ≈ 160 groups × 5 same-make pairs = **800 positives**.
- 400 cross-make 0.5 pairs.
- 400 canonical-query-form pairs (300 English + 100 Hinglish).
- 400 negatives.
- Subtotal: **~2,000 pairs**.

**Risks:**
- bikespares has empty `vehicle_make` for many docs (seen at offset 13500). Fall back to regex-extracting make from the name ("tvs-apache-rtr180" → TVS). Document the regex.
- Ambiguous `system=""` rows (seen in bikespares) — drop, don't guess.
- Same-make cross-model may be false positive (a Bajaj Pulsar fender ≠ Bajaj XCD fender *dimensionally*). That's why cross-model defaults to 0.5, not 1.0, for same-make/diff-model when model field exists.

### 3.4 Strategy D — Symptom / Hindi reinforcements (LIGHTWEIGHT)

Phase 3 already has strong symptom coverage (196 symptom pairs, +68% lift on symptom slice). Phase 3b **does not expand symptom aggressively** — instead, add a small Hindi-catalog-bridge batch:

**Goal:** teach "hawa ka filter for Maruti Swift" ↔ eauto-style catalog "Air Filter for Maruti Swift".

**Source:** vocabulary `SYNONYM_PAIRS_RAW` + catalog docs matching the English side of each pair.

**Generation rule:** for each of the ~40 English→Hindi synonyms that has a catalog hit, emit 1 "Hindi query" ↔ "real catalog name" pair → **1.0** → `pair_type="hindi_catalog_bridge"`.

**Estimated count:** 40 pairs × 3 catalog hits each = **~120 pairs**. Small; directly targets the Hindi −10pt slice without re-running Aksharantar (which failed in v4).

### 3.5 Strategy E — Negatives booster (rebalance)

The golden-v2 set has 12,560 negatives out of 26,760 (47%). Strategies A–D generate mostly positives. To keep the positive:negative ratio roughly stable after inclusion, add:

- ~2,000 hard negatives: (`<product A>`, `<product B>`) from same vehicle but different part systems. Pulled from the existing catalog groups.
- `pair_type="catalog_hard_negative"`, label **0.0**.

---

## 4. γ pair-set composition (summary)

| Strategy | Positive (1.0) | Related (0.5) | Negative (0.0) | Subtotal |
|---|---|---|---|---|
| A — PN ⇄ name | 12,000 | — | 4,000 | 16,000 |
| B — brand-as-generic | 450 | — | 150 | 600 |
| C — vehicle-compatible | 1,200 | 400 | 400 | 2,000 |
| D — Hindi-catalog bridge | 120 | — | — | 120 |
| E — hard negatives | — | — | 2,000 | 2,000 |
| **γ total (new pairs only)** | **13,770** | **400** | **6,550** | **~20,700** |

If Strategy A is capped harder (recommended — 4K PN positives instead of 12K to avoid dominating), γ lands at **~8–10K new pairs** — squarely inside the 3–8K "target sweet-spot" that the prompt specified (actually slightly over; see §6).

**Merged with golden-v2:** golden-v2 (26,760) + γ-capped (~9K) ≈ **~35K pairs**, label distribution roughly: 1.0 ≈ 13K, 0.5 ≈ 5K, 0.85/0.4 HSN unchanged, 0.0 ≈ 16K.

**Path:** `data/training/experiments/2026-04-15-gamma-catalog/gamma_pairs.jsonl`. Merge via a new `scripts/build_gamma.py` modeled on `scripts/merge_v2_pairs.py`.

---

## 5. Target pair count: 3–8K vs the numbers above

The prompt specified **3–8K**. Strict interpretation — strategy A capped to 3K PN pairs, strategy B at 600, C at 2K, D at 120, E at 2K = **~7.7K pairs**. That matches the budget.

**Recommendation:** **γ = ~7K pairs, Strategy-A-capped-hard.** Rationale:
- At ~7K new pairs on top of the 26.7K base, the catalog signal is ≈ 20% of the training distribution — meaningful but not dominant.
- If γ underperforms gate and we need more signal (γ' step), we can expand Strategy A uncapped (still cheap: it's deterministic per seed, rerun time is minutes).
- Keeps training time on Colab T4 under 2 hours per run.

---

## 6. Label scheme (restate — follows ADR 013 + golden-v2)

| Label | Meaning | Used by |
|---|---|---|
| 1.0 | Synonym / direct alias | A.1-3, B.1-2, C.1 + C.3, D |
| 0.5 | Related but not identical (different-model same-make; short-desc alias; cross-make same-system) | A.4, C.2 |
| 0.0 | Negative | A.5, B.3, C.4, E |

Deterministic: every generator uses `random.Random(42)` per ADR 009.

---

## 7. Risks — rolled up

1. **Catalog bias toward Skoda PNs.** ~50% of our catalog is SparesHub Skoda OEM. Strategy A without a cap would make the model a Skoda-PN lookup model, not a general search model. **Mitigation:** cap Strategy A at 3K pairs, stratify by PN prefix.
2. **eauto `vehicle_model` is sparse** (mostly empty). Strategy C collapses to (system, make) granularity, losing the finer synonym signal. **Mitigation:** add a post-processing pass that extracts model names from product text via regex (common models hardcoded: Splendor, Pulsar, Activa, Shine, Apache, Bullet, Swift, i20, City, Creta, Nexon, Baleno).
3. **bikespares schema is noisy** (empty make/model/system). Likely yields low-quality C-strategy pairs. **Mitigation:** drop bikespares from Strategy C; keep it only for A (no PNs → drop) and D.
4. **Negatives are "easy"** if sampled from far-apart systems. Round-2 showed hybrid struggles with catalog-heavy data — we need hard negatives. **Mitigation:** Strategy E targets same-vehicle-different-system, not random.
5. **brand_as_generic seed is 22 pairs.** Too small to generalize — the model may memorize. **Mitigation:** auto-mine brands from catalog (§3.2) to get closer to 50 seed brands.
6. **No BM25-tuned-hybrid evaluation harness yet?** — if round-2 was run ad-hoc, ensure a reproducible eval script exists *before* γ training. (Track this as an implicit T-task in the plan that bootstraps Phase 3b.)
7. **Skoda PN format sometimes has attached suffixes** (e.g. "1T0959702E Z1Y WIND.MOT.", "5J5820045B QWA CONTROLS", "5J5805DIRACKIT RAP LOCK CARRIER..."). Regex must be robust to both `\b[0-9A-Z]{8,13}\b` and trailing color/variant codes. Manually inspect 50 extracted PNs before scaling.
8. **Round-2 dev vs sealed-test discipline.** γ training tuning and model selection happens only on dev. Test set stays sealed until a single publication-time evaluation.

---

## 8. γ' (deferred; scope only)

Triggered ONLY if γ lands in [+3%, +5%] — promising but sub-gate. γ' options:
- Expand Strategy A uncapped (adds ~10K more PN pairs).
- Auto-mine 30 more brand-generic seed pairs from catalog co-occurrence.
- Add Hindi transliteration of SparesHub PNs (pronunciation pairs) — LOW confidence; only if A shows it's the weak link.

Do NOT do γ' if γ is below +3% — that signals the base model or recipe is the bottleneck, not the pair data. In that case, revisit the base-model survey (2026-04-15-base-model-survey.md) and try a different base.

---

## 9. Open questions for the user

1. Cap Strategy A at 3K pairs (recommended) or let it run to 12K and just rebalance negatives? **Recommendation: cap.**
2. Include LLM-generated brand-expansion seeds? ADR 015 warned LLM-generated content hurt v4. **Recommendation: NO. Only auto-mine from real catalog.**
3. Should γ training also try a different base (EmbeddingGemma / gte-multilingual) instead of BGE-m3? Per base-model survey, EmbeddingGemma is top candidate. **Recommendation: train γ on both BGE-m3 (for apples-to-apples with v3) AND on the top base-survey candidate, pick best-on-dev.**
4. `vehicle_model` regex list — approve the 13 models listed in Risk #2, or expand?

---

**File:** `/Users/mac/Projects/auto-parts-search/context/plans/gamma-pair-mining-spec.md`
**Next:** user approval → new ADR 017 (this plan references it) → implementation task under Phase 3b.

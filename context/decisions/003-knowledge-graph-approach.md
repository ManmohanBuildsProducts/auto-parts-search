# Decision 003: Knowledge Graph Before Embeddings

**Date**: 2026-04-09
**Status**: Decided

## Context
Original plan: scrape catalogs → generate pairs → fine-tune model. Discovery of government/educational data sources changes the approach.

## Decision
Build a knowledge graph BEFORE training the embedding model. The graph encodes domain relationships that the model learns to represent in vector space.

## Why This Matters
Without the graph, we get "better fuzzy search" — shocker ≈ shock absorber.
With the graph, we get "auto parts intelligence":
- Part hierarchy (brake pad and brake disc are siblings under Braking System)
- Diagnostic chains (grinding noise → worn brake pad → replace pad + inspect disc)
- Compatibility (this brake pad fits Swift 2019 but not Creta)
- Cross-references (Maruti OEM 16510M68K00 = Bosch F002H234FF)

## Graph Schema
```
Nodes: Part, Category, System, Vehicle, Symptom, Alias
Edges: is_a, in_system, caused_by, fits, equivalent_to, known_as
```

## Impact on Training
- Graded similarity (not just binary) based on graph distance
- Multi-type training pairs from different edge types
- Potentially multi-task loss functions per edge type

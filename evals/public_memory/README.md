# Public memory retrieval benchmarks

This package adds two fast, provider-free checks for conversational-memory retrieval. Dataset
files are downloaded to `.cache/public-benchmarks/memory`, verified by SHA-256 and left untracked.
Generated reports are written to `reports/public/memory`.

## Quick run

```bash
make public-memory-smoke
```

The smoke target selects 100 deterministic queries from each dataset. Run the complete eligible
query sets with:

```bash
make public-memory-locomo
make public-memory-longmemeval
```

Both commands run the previous token-overlap baseline, a dependency-free BM25 reference and the
runtime `HybridMemoryRetriever` with deterministic fake vectors. The fake-vector variant validates
fusion and ranking changes without calling a model API or requiring PostgreSQL; it does not measure
the semantic quality of the configured production embedding model.

## LoCoMo

The adapter uses the official `locomo10.json`. Each conversation session is a retrievable memory
record. Official evidence IDs such as `D3:7` are mapped to session 3. Questions without evidence
are excluded from retrieval scoring.

This is a public LoCoMo evaluation adaptation, but it is session retrieval rather than the full
paper QA protocol. Report it as “session retrieval on LoCoMo” and include the adapter settings.

## LongMemEval Oracle Mix

The cleaned `longmemeval_oracle.json` contains evidence sessions, not the full LongMemEval haystack.
The adapter adds 31 sessions sampled from other examples as distractors using a fixed seed. Official
abstention questions are excluded, consistent with retrieval-only evaluation.

This is useful for a fast regression check. It is a derived task and **must not be presented as an
official LongMemEval or paper-comparable score**. A paper-comparable run requires the official S/M
haystack data and retrieval protocol.

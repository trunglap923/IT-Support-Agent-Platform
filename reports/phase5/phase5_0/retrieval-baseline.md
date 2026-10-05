# Retrieval benchmark — Phase 5.0 evaluation

Run against an isolated, freshly migrated PostgreSQL/pgvector database at
`2026-09-16T00:00:00+00:00` using corpus `m2-corpus-v1`.

Configuration: reranker `weighted_feature_v1`, candidate pool 20, neighbor/parent expansion up to 2 neighbors per seed, max 5 citations and 6000 estimated context tokens.

| Metric | Numerator | Denominator | Result |
|---|---:|---:|---:|
| Recall@5 | 31.0 | 31 | 1.000 |
| Precision@5 (document-version) | 6.800 | 31 | 0.219 |
| MRR@5 (sum RR / answerable) | 29.500 | 31 | 0.952 |
| nDCG@5 | 29.580 | 31 | 0.954 |
| Duplicate rate@5 | 15.200 | 42 | 0.362 |
| Historical-version known gap | 0 | 2 | 0.000 |
| No-answer accuracy | 6 | 6 | 1.000 |
| Scope leakage | 0 | 3 | 0.000 |
| Expected document cited | 22 | 31 | 0.710 |
| Expected chunk recall@5 | 29 | 31 | 0.935 |
| Expected chunk cited | 21 | 31 | 0.677 |
| Citation precision | 21 | 31 | 0.677 |

G-04 (`Recall@5 >= 0.85`): **PASS**.

Context: average 7.43 expanded chunks per query; average
0.74 selected citations; average 72
estimated citation context tokens (maximum observed 310, budget
6000).

Answerable misses: none.
No-answer false positives: none.

## Limitations

- Fake hash embeddings validate wiring and reproducibility, not semantic quality.
- Historical version requests are measured as a known gap and excluded from the release gate.
- Precision and duplicate rate are measured at document-version level.
- No-answer uses the retrieval/citation threshold; claim support needs WP-06.
- Chunk labels match section plus required terms and do not provide claim-level entailment judgments.
- The dataset is development-only and must not be treated as a holdout set.

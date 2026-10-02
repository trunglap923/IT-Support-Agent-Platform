# Retrieval benchmark — Phase 3

Run against an isolated, freshly migrated PostgreSQL/pgvector database at
`2026-09-16T00:00:00+00:00` using corpus `m2-corpus-v1`.

Configuration: reranker `weighted_feature_v1`, candidate pool 20, neighbor/parent expansion up to 2 neighbors per seed, max 5 citations and 6000 estimated context tokens.

| Metric | Numerator | Denominator | Result |
|---|---:|---:|---:|
| Recall@5 | 13.0 | 13 | 1.000 |
| Precision@5 (document-version) | 2.800 | 13 | 0.215 |
| MRR@5 (sum RR / answerable) | 12.000 | 13 | 0.923 |
| nDCG@5 | 12.262 | 13 | 0.943 |
| Duplicate rate@5 | 8.400 | 22 | 0.382 |
| Historical-version known gap | 0 | 2 | 0.000 |
| No-answer accuracy | 5 | 5 | 1.000 |
| Scope leakage | 0 | 2 | 0.000 |
| Expected document cited | 9 | 13 | 0.692 |

G-04 (`Recall@5 >= 0.85`): **PASS**.

Phase 3 context: average 7.00 expanded chunks per query; average
0.68 selected citations; average 66
estimated citation context tokens (maximum observed 310, budget
6000).

Answerable misses: none.
No-answer false positives: none.

## Limitations

- Fake hash embeddings validate wiring and reproducibility, not semantic quality.
- Historical version requests are measured as a known gap and excluded from the release gate.
- Precision and duplicate rate are measured at document-version level.
- No-answer uses the retrieval/citation threshold; claim support needs WP-06.
- Citation quality is measured against expected document/version labels; chunk-level claim support is not labeled.
- The dataset is development-only and must not be treated as a holdout set.

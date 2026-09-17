# Retrieval baseline — M2

Run against an isolated, freshly migrated PostgreSQL/pgvector database at
`2026-09-16T00:00:00+00:00` using corpus `m2-corpus-v1`.

| Metric | Numerator | Denominator | Result |
|---|---:|---:|---:|
| Recall@5 | 10 | 10 | 1.000 |
| MRR@5 (sum RR / answerable) | 9.500 | 10 | 0.950 |
| No-answer accuracy | 5 | 5 | 1.000 |
| Scope leakage | 0 | 2 | 0.000 |

G-04 (`Recall@5 >= 0.85`): **PASS**.

Answerable misses: none.
No-answer false positives: none.

## Limitations

- Fake hash embeddings validate wiring and reproducibility, not semantic quality.
- No-answer uses the retrieval/citation threshold; claim support needs WP-06.
- The dataset is development-only and must not be treated as a holdout set.

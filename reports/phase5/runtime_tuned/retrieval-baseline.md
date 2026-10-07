# Retrieval benchmark — weighted reranker

Run against an isolated, freshly migrated PostgreSQL/pgvector database at
`2026-09-16T00:00:00+00:00` using corpus `m2-corpus-v1`.

Configuration: embedding `fake:fake-embedding-v2`,
chunking `500/60`,
reranker `fusion_score`, candidate pool 20, neighbor/parent expansion up to 2 neighbors per seed, max 5 citations and 6000 estimated context tokens.

| Metric | Numerator | Denominator | Result |
|---|---:|---:|---:|
| Recall@5 | 31.0 | 31 | 1.000 |
| Precision@5 (document-version) | 6.800 | 31 | 0.219 |
| MRR@5 (sum RR / answerable) | 28.500 | 31 | 0.919 |
| nDCG@5 | 28.989 | 31 | 0.935 |
| Duplicate rate@5 | 0.000 | 42 | 0.000 |
| Historical-version known gap | 0 | 2 | 0.000 |
| No-answer accuracy | 6 | 6 | 1.000 |
| Scope leakage | 0 | 3 | 0.000 |
| Expected document cited | 21 | 31 | 0.677 |
| Expected chunk recall@5 | 25 | 31 | 0.806 |
| Expected chunk cited | 21 | 31 | 0.677 |
| Citation precision | 21 | 28 | 0.750 |

G-04 (`Recall@5 >= 0.85`): **PASS**.

Context: average 13.52 expanded chunks per query; average
0.67 selected citations; average 67
estimated citation context tokens (maximum observed 310, budget
6000).

Answerable misses: none.
No-answer false positives: none.

## Primary candidate score distributions

| Signal | Positive count | Positive median | Negative count | Negative median |
|---|---:|---:|---:|---:|
| score | 25 | 0.6667 | 175 | 0.1667 |
| vector_similarity | 25 | 0.4003 | 175 | 0.1400 |
| lexical_coverage | 25 | 0.6667 | 175 | 0.1250 |
| rrf_score | 25 | 0.0205 | 175 | 0.0190 |
| rerank_score | 25 | 1.0000 | 175 | 0.9385 |
| exact_match_score | 25 | 0.7778 | 133 | 0.1818 |
| metadata_score | 25 | 0.0000 | 175 | 0.0000 |
| evidence_score | 25 | 0.6934 | 175 | 0.2811 |

## Evidence threshold sweep

Recommended threshold: **0.50**.

| Threshold | Document citation | Chunk citation | Citation precision | No-answer accuracy | Scope leakage | Eligible |
|---:|---:|---:|---:|---:|---:|:---:|
| 0.20 | 1.0000 | 0.9355 | 0.2042 | 0.0000 | 0.0000 | no |
| 0.25 | 1.0000 | 0.9032 | 0.2188 | 0.1667 | 0.0000 | no |
| 0.30 | 0.9355 | 0.8710 | 0.3333 | 0.1667 | 0.0000 | no |
| 0.35 | 0.8710 | 0.8387 | 0.4333 | 0.5000 | 0.0000 | no |
| 0.40 | 0.8065 | 0.7742 | 0.5854 | 0.8333 | 0.0000 | no |
| 0.45 | 0.7742 | 0.7742 | 0.7059 | 0.8333 | 0.0000 | no |
| 0.50 | 0.6774 | 0.6774 | 0.7500 | 1.0000 | 0.0000 | yes |
| 0.55 | 0.6452 | 0.6452 | 0.7407 | 1.0000 | 0.0000 | yes |
| 0.60 | 0.6129 | 0.6129 | 0.7917 | 1.0000 | 0.0000 | yes |
| 0.65 | 0.5161 | 0.5161 | 0.7619 | 1.0000 | 0.0000 | yes |
| 0.70 | 0.3871 | 0.3871 | 0.8571 | 1.0000 | 0.0000 | yes |

## Limitations

- Fake hash embeddings validate wiring and reproducibility, not semantic quality.
- Historical version requests are measured as a known gap and excluded from the release gate.
- Precision and duplicate rate are measured at document-version level.
- No-answer uses the retrieval/citation threshold; claim support needs WP-06.
- Chunk labels match section plus required terms and do not provide claim-level entailment judgments.
- The dataset is development-only and must not be treated as a holdout set.

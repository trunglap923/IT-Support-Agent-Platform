# Retrieval benchmark — weighted reranker

Run against an isolated, freshly migrated PostgreSQL/pgvector database at
`2026-09-16T00:00:00+00:00` using corpus `m2-corpus-v1`.

Configuration: embedding `fake:fake-embedding-v2`,
chunking `500/60`,
reranker `weighted_feature_v1`, candidate pool 20, neighbor/parent expansion up to 2 neighbors per seed, max 5 citations and 6000 estimated context tokens.

| Metric | Numerator | Denominator | Result |
|---|---:|---:|---:|
| Recall@5 | 31.0 | 31 | 1.000 |
| Precision@5 (document-version) | 6.800 | 31 | 0.219 |
| MRR@5 (sum RR / answerable) | 29.500 | 31 | 0.952 |
| nDCG@5 | 29.580 | 31 | 0.954 |
| Duplicate rate@5 | 0.000 | 42 | 0.000 |
| Historical-version known gap | 0 | 2 | 0.000 |
| No-answer accuracy | 6 | 6 | 1.000 |
| Scope leakage | 0 | 3 | 0.000 |
| Expected document cited | 22 | 31 | 0.710 |
| Expected chunk recall@5 | 30 | 31 | 0.968 |
| Expected chunk cited | 22 | 31 | 0.710 |
| Citation precision | 22 | 29 | 0.759 |

G-04 (`Recall@5 >= 0.85`): **PASS**.

Context: average 14.10 expanded chunks per query; average
0.69 selected citations; average 69
estimated citation context tokens (maximum observed 310, budget
6000).

Answerable misses: none.
No-answer false positives: none.

## Primary candidate score distributions

| Signal | Positive count | Positive median | Negative count | Negative median |
|---|---:|---:|---:|---:|
| score | 31 | 0.6667 | 169 | 0.1667 |
| vector_similarity | 31 | 0.3518 | 164 | 0.1205 |
| lexical_coverage | 31 | 0.6667 | 169 | 0.1250 |
| rrf_score | 31 | 0.0492 | 169 | 0.0451 |
| rerank_score | 31 | 0.6476 | 169 | 0.2539 |
| exact_match_score | 31 | 0.7692 | 145 | 0.2000 |
| metadata_score | 31 | 1.0000 | 169 | 0.5000 |
| evidence_score | 31 | 0.6354 | 169 | 0.1769 |

## Evidence threshold sweep

Recommended threshold: **0.45**.

| Threshold | Document citation | Chunk citation | Citation precision | No-answer accuracy | Scope leakage | Eligible |
|---:|---:|---:|---:|---:|---:|:---:|
| 0.20 | 0.9677 | 0.9677 | 0.3298 | 0.3333 | 0.0000 | no |
| 0.25 | 0.9032 | 0.9032 | 0.4143 | 0.6667 | 0.0000 | no |
| 0.30 | 0.8710 | 0.8710 | 0.4746 | 0.6667 | 0.0000 | no |
| 0.35 | 0.8065 | 0.8065 | 0.6410 | 0.8333 | 0.0000 | no |
| 0.40 | 0.7742 | 0.7742 | 0.7273 | 0.8333 | 0.0000 | no |
| 0.45 | 0.7097 | 0.7097 | 0.7586 | 1.0000 | 0.0000 | yes |
| 0.50 | 0.7097 | 0.7097 | 0.7586 | 1.0000 | 0.0000 | yes |
| 0.55 | 0.6774 | 0.6774 | 0.8077 | 1.0000 | 0.0000 | yes |
| 0.60 | 0.5806 | 0.5806 | 0.7826 | 1.0000 | 0.0000 | yes |
| 0.65 | 0.4839 | 0.4839 | 0.7895 | 1.0000 | 0.0000 | yes |
| 0.70 | 0.3226 | 0.3226 | 0.7692 | 1.0000 | 0.0000 | yes |

## Limitations

- Fake hash embeddings validate wiring and reproducibility, not semantic quality.
- Historical version requests are measured as a known gap and excluded from the release gate.
- Precision and duplicate rate are measured at document-version level.
- No-answer uses the retrieval/citation threshold; claim support needs WP-06.
- Chunk labels match section plus required terms and do not provide claim-level entailment judgments.
- The dataset is development-only and must not be treated as a holdout set.

# Retrieval benchmark — weighted reranker

Run against an isolated, freshly migrated PostgreSQL/pgvector database at
`2026-09-16T00:00:00+00:00` using corpus `m2-corpus-v1`.

Configuration: embedding `openai:text-embedding-3-small`,
chunking `500/60`,
reranker `weighted_feature_v1`, candidate pool 20, neighbor/parent expansion up to 2 neighbors per seed, max 5 citations and 6000 estimated context tokens.

| Metric | Numerator | Denominator | Result |
|---|---:|---:|---:|
| Recall@5 | 31.0 | 31 | 1.000 |
| Precision@5 (document-version) | 6.800 | 31 | 0.219 |
| MRR@5 (sum RR / answerable) | 29.333 | 31 | 0.946 |
| nDCG@5 | 29.449 | 31 | 0.950 |
| Duplicate rate@5 | 0.000 | 42 | 0.000 |
| Historical-version known gap | 0 | 2 | 0.000 |
| No-answer accuracy | 6 | 6 | 1.000 |
| Scope leakage | 0 | 3 | 0.000 |
| Expected document cited | 24 | 31 | 0.774 |
| Expected chunk recall@5 | 31 | 31 | 1.000 |
| Expected chunk cited | 24 | 31 | 0.774 |
| Citation precision | 24 | 33 | 0.727 |

G-04 (`Recall@5 >= 0.85`): **PASS**.

Context: average 14.24 expanded chunks per query; average
0.79 selected citations; average 79
estimated citation context tokens (maximum observed 310, budget
6000).

Answerable misses: none.
No-answer false positives: none.

## Primary candidate score distributions

| Signal | Positive count | Positive median | Negative count | Negative median |
|---|---:|---:|---:|---:|
| score | 32 | 0.6667 | 168 | 0.3399 |
| vector_similarity | 32 | 0.6001 | 164 | 0.3399 |
| lexical_coverage | 32 | 0.6250 | 168 | 0.1250 |
| rrf_score | 32 | 0.0492 | 168 | 0.0449 |
| rerank_score | 32 | 0.6520 | 168 | 0.2651 |
| exact_match_score | 32 | 0.7500 | 144 | 0.2000 |
| metadata_score | 32 | 1.0000 | 168 | 0.5000 |
| evidence_score | 32 | 0.6560 | 168 | 0.2189 |

## Evidence threshold sweep

Recommended threshold: **0.45**.

| Threshold | Document citation | Chunk citation | Citation precision | No-answer accuracy | Scope leakage | Eligible |
|---:|---:|---:|---:|---:|---:|:---:|
| 0.20 | 1.0000 | 1.0000 | 0.2759 | 0.1667 | 0.0000 | no |
| 0.25 | 0.9355 | 0.9355 | 0.3529 | 0.6667 | 0.0000 | no |
| 0.30 | 0.9355 | 0.9355 | 0.4348 | 0.6667 | 0.0000 | no |
| 0.35 | 0.8710 | 0.8710 | 0.5490 | 0.6667 | 0.0000 | no |
| 0.40 | 0.8065 | 0.8065 | 0.6757 | 0.8333 | 0.0000 | no |
| 0.45 | 0.7742 | 0.7742 | 0.7273 | 1.0000 | 0.0000 | yes |
| 0.50 | 0.7097 | 0.7097 | 0.7586 | 1.0000 | 0.0000 | yes |
| 0.55 | 0.7097 | 0.7097 | 0.7586 | 1.0000 | 0.0000 | yes |
| 0.60 | 0.6452 | 0.6452 | 0.8000 | 1.0000 | 0.0000 | yes |
| 0.65 | 0.5806 | 0.5806 | 0.7826 | 1.0000 | 0.0000 | yes |
| 0.70 | 0.4194 | 0.4194 | 0.8125 | 1.0000 | 0.0000 | yes |

## Limitations

- Production embeddings incur provider cost and remain corpus-specific.
- Historical version requests are measured as a known gap and excluded from the release gate.
- Precision and duplicate rate are measured at document-version level.
- No-answer uses the retrieval/citation threshold; claim support needs WP-06.
- Chunk labels match section plus required terms and do not provide claim-level entailment judgments.
- The dataset is development-only and must not be treated as a holdout set.

# Phase 5.3A — Chunking and score-distribution benchmark

All three offline runs use the deterministic fake embedding provider and the weighted reranker.

| Chunk target/overlap | Recall@5 | Precision@5 | MRR@5 | nDCG@5 | Chunk recall@5 | Chunk citation | No-answer accuracy | Scope leakage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 120/20 | 1.0000 | 0.2194 | 0.9516 | 0.9542 | 0.9355 | 0.6774 | 1.0000 | 0.0000 |
| 300/40 | 1.0000 | 0.2194 | 0.9516 | 0.9542 | 0.9355 | 0.6774 | 1.0000 | 0.0000 |
| 500/60 | 1.0000 | 0.2194 | 0.9516 | 0.9542 | 0.9355 | 0.6774 | 1.0000 | 0.0000 |

## Primary score separation

The distributions are identical because every evaluated structural section fits below the
smallest 120-token target. The section-aware splitter therefore produces the same leaf chunks
for all three configurations.

| Signal | Positive median | Negative median | Median gap |
|---|---:|---:|---:|
| Query-term coverage | 0.6250 | 0.1250 | 0.5000 |
| Vector similarity | 0.3341 | 0.1205 | 0.2136 |
| RRF score | 0.0328 | 0.0302 | 0.0026 |
| Rerank score | 0.5930 | 0.2219 | 0.3711 |

Full positive and negative distributions, including min, p10, p25, median, p75, p90,
maximum, mean, and sample count, are stored in each run's `retrieval-baseline.json` under
`score_distributions`.

## Production embedding run

The production run is intentionally gated by `RUN_PAID_RETRIEVAL_BENCHMARK=true`. It was not
executed in this change because the approval boundary for exporting the internal evaluation
corpus and queries to the external embedding API was not granted. The benchmark runner is ready
for that explicit, separately approved run.

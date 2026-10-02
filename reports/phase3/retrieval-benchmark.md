# Phase 3 retrieval benchmark

Compared the recorded Phase 2 baseline with Phase 3 on the same 22 development cases, corpus manifest, parser/chunker versions, and fake embedding provider. The Phase 3 run used an isolated, freshly migrated PostgreSQL database.

| Metric | Phase 2 | Phase 3 | Delta |
|---|---:|---:|---:|
| Recall@5 | 1.000 | 1.000 | +0.000 |
| Precision@5 | 0.215 | 0.215 | +0.000 |
| MRR@5 | 0.923 | 0.923 | +0.000 |
| nDCG@5 | 0.943 | 0.943 | +0.000 |
| Duplicate rate@5 | 0.336 | 0.382 | +0.045 |
| No-answer accuracy | 1.000 | 1.000 | +0.000 |
| Scope leakage | 0.000 | 0.000 | +0.000 |

## Phase 3-specific measurements

- Context expansion added 154 chunks total, averaging 7.00 per query (maximum 11).
- Expected document/version appeared in selected citations for 9/13 answerable cases (0.692). Misses: ret-005, ret-018, ret-019, ret-022.
- Citation context averaged 66 estimated tokens per case and peaked at 310 against the 6000 budget.
- Top-five document ordering changed in 14/22 cases; the expected-document rank did not change in any case.

## Reading the result

Recall, MRR and nDCG match the Phase 2 baseline. The reranker did not improve document ranking on this dataset. Duplicate rate rose from 0.336 to 0.382, so the current chunk ranking has more repeated document versions in top five. The run still passes the existing Recall@5 gate and has no-answer accuracy 1.0 and scope leakage 0.

The citation selection measurement exposes cases where retrieval found an expected document but citation support/selection did not include it. In particular, `ret-005` returned an answer with only the escalation source selected; `ret-018`, `ret-019`, and `ret-022` were classified no-answer despite the expected document appearing in top five. The 6,000-token budget was not close to binding (maximum observed 310), so it did not constrain this sample.

This is a development dataset with fake embeddings and sparse document-level labels. It verifies deterministic wiring and safety gates; it does not establish semantic quality or claim-level citation support. The recorded Phase 2 baseline was not rerun as a same-process ablation, so the comparison is against its committed artifact.

Detailed run: [retrieval-baseline.md](retrieval-baseline.md) and [retrieval-baseline.json](retrieval-baseline.json). Machine-readable comparison: [retrieval-benchmark.json](retrieval-benchmark.json).

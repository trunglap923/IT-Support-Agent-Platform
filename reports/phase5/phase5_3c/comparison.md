# Phase 5.3C — Evidence selection comparison

Compared with Phase 5.3B at the calibrated evidence threshold `0.45`.

| Metric | Phase 5.3B | Phase 5.3C | Change |
|---|---:|---:|---:|
| Recall@5 | 1.0000 | 1.0000 | 0.0000 |
| Expected chunk recall@5 | 0.9677 | 0.9677 | 0.0000 |
| Expected document citation rate | 0.7097 | 0.7097 | 0.0000 |
| Expected chunk citation rate | 0.7097 | 0.7097 | 0.0000 |
| Citation precision | 0.7097 | 0.7586 | +0.0489 |
| Selected citations per case | 0.7381 | 0.6905 | -0.0476 |
| Average citation context tokens | 72.43 | 69.24 | -3.19 |
| No-answer accuracy | 1.0000 | 1.0000 | 0.0000 |
| Scope leakage | 0.0000 | 0.0000 | 0.0000 |

Primary and expanded chunks are deduplicated into one evidence pool. Each hit receives an
`evidence_score` from lexical coverage, vector similarity, reranker score, exact-match score,
and metadata score. Citation selection ranks the merged pool by this score before applying the
source-count, near-duplicate, and context-token budgets.

The automatic sweep evaluates thresholds from `0.20` through `0.70`. It first rejects thresholds
that reduce no-answer accuracy or introduce scope leakage, then maximizes chunk citation rate,
citation precision, and document citation rate. The lowest threshold wins exact metric ties.
The resulting recommendation is `0.45`.

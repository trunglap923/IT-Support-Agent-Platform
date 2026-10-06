# Phase 5.3B — Candidate quality comparison

Compared with the Phase 5.3A `500/60` offline baseline.

| Metric | Phase 5.3A | Phase 5.3B | Change |
|---|---:|---:|---:|
| Recall@5 | 1.0000 | 1.0000 | 0.0000 |
| Precision@5 | 0.2194 | 0.2194 | 0.0000 |
| MRR@5 | 0.9516 | 0.9516 | 0.0000 |
| nDCG@5 | 0.9542 | 0.9542 | 0.0000 |
| Expected chunk recall@5 | 0.9355 | 0.9677 | +0.0322 |
| Expected chunk citation rate | 0.6774 | 0.7097 | +0.0323 |
| Citation precision | 0.6774 | 0.7097 | +0.0323 |
| No-answer accuracy | 1.0000 | 1.0000 | 0.0000 |
| Scope leakage | 0.0000 | 0.0000 | 0.0000 |

## ret-039

The expected `engineering-oncall:v1` / `Registry incident` chunk is rank 1 and is selected as
evidence. The previous false miss came from the evaluator comparing `service status dashboard`
against Markdown text containing a line break between `status` and `dashboard`. Relevant-chunk
matching now normalizes structural whitespace before applying the required-term labels.

## Candidate signals

The exact branch searches literal tokens across document key, title, version, section, and chunk
content while retaining the shared ACL and current-version predicates. Metadata extracted by the
query analyzer is applied as a soft reranking feature. Adaptive diversity permits a second strong
chunk from the same document when it belongs to the same section or carries an exact identifier.

# Phase 5.1 document diversity comparison

Phase 5.1 limits primary retrieval results to one chunk for each document version. Parent
and neighboring chunks remain available as context expansion after seed selection.

Both runs used the same 42 cases, corpus snapshot, fake embedding provider, candidate limits,
reranker, and PostgreSQL database setup.

| Metric | Phase 5.0 | Phase 5.1 | Delta |
|---|---:|---:|---:|
| Recall@5 | 1.000 | 1.000 | +0.000 |
| Precision@5 | 0.219 | 0.219 | +0.000 |
| MRR@5 | 0.952 | 0.952 | +0.000 |
| nDCG@5 | 0.954 | 0.954 | +0.000 |
| Duplicate rate@5 | 0.362 | 0.000 | -0.362 |
| Expected document citation rate | 0.710 | 0.710 | +0.000 |
| Expected chunk recall@5 | 0.935 | 0.935 | +0.000 |
| Expected chunk citation rate | 0.677 | 0.677 | +0.000 |
| Citation precision | 0.677 | 0.677 | +0.000 |
| Scope leakage | 0.000 | 0.000 | +0.000 |

The diversity selector removes repeated document versions from primary top-five results on
this dataset without reducing document recall, chunk recall, citation selection, or ACL safety.
It remains configurable through `RETRIEVAL_MAX_PRIMARY_CHUNKS_PER_DOCUMENT`.

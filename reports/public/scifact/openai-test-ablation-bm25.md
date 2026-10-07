# Public retrieval ablation

Full official split: `true`

| Variant | nDCG@10 | MAP@10 | Recall@5 | Recall@10 | MRR@10 |
|---|---:|---:|---:|---:|---:|
| dense_only | 0.7111 | 0.6612 | 0.7663 | 0.8526 | 0.6736 |
| postgres_fts_only | 0.2723 | 0.2301 | 0.3119 | 0.3997 | 0.2355 |
| bm25_only | 0.6795 | 0.6349 | 0.7336 | 0.8030 | 0.6452 |
| hybrid_postgres_rrf | 0.5998 | 0.5521 | 0.6667 | 0.7328 | 0.5647 |
| hybrid_postgres_weighted | 0.5584 | 0.5052 | 0.6306 | 0.7128 | 0.5134 |
| hybrid_bm25_rrf | 0.6837 | 0.6359 | 0.7592 | 0.8177 | 0.6473 |
| hybrid_bm25_weighted | 0.5856 | 0.5312 | 0.6522 | 0.7428 | 0.5403 |
| hybrid_bm25_train_tuned | 0.7318 | 0.6863 | 0.7897 | 0.8569 | 0.7003 |

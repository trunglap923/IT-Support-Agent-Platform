# Public retrieval ablation

Full official split: `true`

| Variant | nDCG@10 | MAP@10 | Recall@5 | Recall@10 | MRR@10 |
|---|---:|---:|---:|---:|---:|
| dense_only | 0.7307 | 0.6853 | 0.8010 | 0.8532 | 0.6984 |
| postgres_fts_only | 0.3238 | 0.2796 | 0.3732 | 0.4506 | 0.2907 |
| bm25_only | 0.6985 | 0.6563 | 0.7371 | 0.8163 | 0.6676 |
| hybrid_postgres_rrf | 0.6431 | 0.5929 | 0.7049 | 0.7827 | 0.6066 |
| hybrid_postgres_weighted | 0.6123 | 0.5650 | 0.6695 | 0.7424 | 0.5786 |
| hybrid_bm25_rrf | 0.7052 | 0.6589 | 0.7495 | 0.8349 | 0.6707 |
| hybrid_bm25_weighted | 0.6159 | 0.5653 | 0.6722 | 0.7579 | 0.5777 |


## Selected fusion weights

- Selection split: `train`
- Objective: `ndcg_at_10`
- Dense weight: `1.0`
- Sparse weight: `0.25`
- Exact weight: `0.0`
- nDCG@10: `0.7533`
- Recall@10: `0.8712`

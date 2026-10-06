# Public retrieval ablation

Full official split: `true`

| Variant | nDCG@10 | MAP@10 | Recall@5 | Recall@10 | MRR@10 |
|---|---:|---:|---:|---:|---:|
| dense_only | 0.3471 | 0.3159 | 0.3697 | 0.4375 | 0.3235 |
| postgres_fts_only | 0.2723 | 0.2301 | 0.3119 | 0.3997 | 0.2355 |
| hybrid_rrf | 0.4880 | 0.4420 | 0.5536 | 0.6150 | 0.4573 |
| hybrid_weighted | 0.5147 | 0.4651 | 0.5622 | 0.6586 | 0.4749 |

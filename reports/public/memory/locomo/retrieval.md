# LoCoMo memory retrieval

- Scope: Session-level retrieval derived from official turn-level evidence labels.
- Paper comparable: **false**
- Evaluated queries: 1982 / 1982
- Indexed records: 272

| Variant | nDCG@10 | MAP@10 | Recall@5 | Recall@10 | MRR@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| lexical | 0.6919 | 0.6212 | 0.7707 | 0.8718 | 0.6537 |
| bm25 | 0.7705 | 0.7121 | 0.8371 | 0.9084 | 0.7462 |
| hybrid_fake | 0.7744 | 0.7156 | 0.8369 | 0.9140 | 0.7496 |

## Interpretation

Session-level retrieval derived from official turn-level evidence labels.

Source: https://github.com/snap-research/locomo

# LoCoMo memory retrieval

- Scope: Session-level retrieval derived from official turn-level evidence labels.
- Paper comparable: **false**
- Evaluated queries: 100 / 1982
- Indexed records: 272

| Variant | nDCG@10 | MAP@10 | Recall@5 | Recall@10 | MRR@10 |
| --- | ---: | ---: | ---: | ---: | ---: |
| lexical | 0.6601 | 0.5785 | 0.7725 | 0.8983 | 0.5883 |
| bm25 | 0.7487 | 0.6886 | 0.8350 | 0.9117 | 0.6999 |
| hybrid_fake | 0.7531 | 0.6936 | 0.8300 | 0.9167 | 0.7029 |

## Interpretation

Session-level retrieval derived from official turn-level evidence labels.

Source: https://github.com/snap-research/locomo

# BEIR SciFact BM25 anchor

- Split: `test`
- Corpus: 5183 whole documents
- Queries: 300
- Full official split: `true`

## Metrics

| Metric | Score |
|---|---:|
| ndcg_at_10 | 0.6762 |
| map_at_10 | 0.6309 |
| recall_at_5 | 0.7403 |
| recall_at_10 | 0.8013 |
| precision_at_10 | 0.0880 |
| mrr_at_10 | 0.6413 |

## External anchor

- System: Anserini flat BM25
- Published nDCG@10: 0.6789
- Absolute difference: -0.0027
- Reproduction page: https://github.com/castorini/anserini/blob/master/docs/reproduce/from-document-collection/beir-v1.0.0-scifact.flat.md

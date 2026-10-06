# BEIR SciFact comparison

Both runs use the complete official SciFact test split: 5,183 corpus documents, 300 queries,
and the relevance judgments distributed by BEIR. The archive was verified with the published
MD5 checksum `5f7d1de60b170fc8027bb7898e2efca1`.

| Metric | Fake hashing baseline | text-embedding-3-small | Absolute change |
|---|---:|---:|---:|
| nDCG@10 | 0.5147 | 0.5584 | +0.0438 |
| MAP@10 | 0.4651 | 0.5052 | +0.0401 |
| Recall@5 | 0.5622 | 0.6306 | +0.0683 |
| Recall@10 | 0.6586 | 0.7128 | +0.0542 |
| Precision@10 | 0.0720 | 0.0783 | +0.0063 |
| MRR@10 | 0.4749 | 0.5134 | +0.0385 |

The evaluated system is this project's full hybrid pipeline: dense retrieval, PostgreSQL full
text retrieval, exact matching, reciprocal rank fusion, weighted feature reranking, and one
result per document. Documents use the production 500-token target with 60-token overlap.

The fake run is a deterministic engineering baseline. The OpenAI run is the result suitable
for describing model-backed retrieval performance. These scores measure SciFact scientific
claim retrieval and must not be presented as IT support domain accuracy. Internal IT support
quality remains covered separately by the versioned regression suite under `evals/cases`.

Detailed provenance, configuration, per-query rankings, relevance labels, metrics, and latency
are recorded in `fake-test-retrieval.json` and `openai-test-retrieval.json`.

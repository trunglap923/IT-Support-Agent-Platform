# BEIR SciFact comparison

Both runs use the complete official SciFact test split: 5,183 corpus documents, 300 queries,
and the relevance judgments distributed by BEIR. The archive was verified with the published
MD5 checksum `5f7d1de60b170fc8027bb7898e2efca1`.

| Metric | Fake hashing hybrid | OpenAI hybrid | Whole-document BM25 |
|---|---:|---:|---:|
| nDCG@10 | 0.5147 | 0.5584 | **0.6762** |
| MAP@10 | 0.4651 | 0.5052 | **0.6309** |
| Recall@5 | 0.5622 | 0.6306 | **0.7403** |
| Recall@10 | 0.6586 | 0.7128 | **0.8013** |
| Precision@10 | 0.0720 | 0.0783 | **0.0880** |
| MRR@10 | 0.4749 | 0.5134 | **0.6413** |

The evaluated system is this project's full hybrid pipeline: dense retrieval, PostgreSQL full
text retrieval, exact matching, reciprocal rank fusion, weighted feature reranking, and one
result per document. Documents use the production 500-token target with 60-token overlap.

The BM25 anchor uses whole documents, English stopwords, English stemming, Lucene BM25,
`k1=0.9`, and `b=0.4`. Its `0.6762` nDCG@10 is within `0.0027` of the independently published
Anserini flat BM25 result (`0.6789`), validating the loader, qrels, and metric calculations.

The fake run is a deterministic engineering baseline. The OpenAI run is the result suitable
for describing model-backed retrieval performance. These scores measure SciFact scientific
claim retrieval and must not be presented as IT support domain accuracy. Internal IT support
quality remains covered separately by the versioned regression suite under `evals/cases`.

## Candidate and ranking ablation

The full fake-embedding run isolates the retrieval branches without another paid API call:

| Variant | nDCG@10 | Recall@10 | MRR@10 |
|---|---:|---:|---:|
| Dense hash only | 0.3471 | 0.4375 | 0.3235 |
| PostgreSQL FTS only | 0.2723 | 0.3997 | 0.2355 |
| Hybrid RRF | 0.4880 | 0.6150 | 0.4573 |
| Hybrid weighted reranker | **0.5147** | **0.6586** | **0.4749** |

The weighted reranker improves RRF by `0.0267` nDCG@10. PostgreSQL FTS trails the verified
whole-document BM25 anchor by `0.4039`, identifying lexical candidate quality as the main
measured bottleneck. The production ablation must be rerun after configuring a valid API key;
the previous key was rejected before corpus indexing, so no partial production result is used.

## Chunking isolation

| BM25 granularity | Indexed units | nDCG@10 | Recall@10 |
|---|---:|---:|---:|
| Whole document | 5,183 | 0.676188 | 0.8013 |
| Production chunks (`500/60`) | 5,263 | 0.676131 | 0.8013 |

Holding tokenization and BM25 scoring constant, production chunking changes nDCG@10 by only
`-0.000057` and leaves Recall@10 unchanged. Chunking is therefore not the measured cause of the
hybrid gap on SciFact. The next retrieval change should replace or supplement PostgreSQL
`ts_rank_cd` with a true BM25 sparse backend.

Detailed provenance, configuration, per-query rankings, relevance labels, metrics, and latency
are recorded in `fake-test-retrieval.json`, `openai-test-retrieval.json`, and
`bm25-test-retrieval.json`. Candidate-level ablation results are in
`fake-test-ablation.json`; the controlled chunking run is in
`bm25-chunked-test-retrieval.json`.

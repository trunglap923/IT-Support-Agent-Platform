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

## Production embedding ablation

The full OpenAI run uses `text-embedding-3-small` and evaluates every branch on the same 300
queries and 5,263 production chunks:

| Variant | nDCG@10 | Recall@10 | MRR@10 |
|---|---:|---:|---:|
| OpenAI dense only | **0.7111** | **0.8526** | **0.6736** |
| Runtime BM25 only | 0.6795 | 0.8030 | 0.6452 |
| PostgreSQL hybrid RRF | 0.6000 | 0.7328 | 0.5648 |
| PostgreSQL hybrid weighted | 0.5584 | 0.7128 | 0.5134 |
| BM25 hybrid RRF | 0.6837 | 0.8177 | 0.6473 |
| BM25 hybrid weighted | 0.5856 | 0.7428 | 0.5403 |

Replacing PostgreSQL FTS with BM25 raises hybrid RRF nDCG@10 by `0.0837` and raises the
current weighted pipeline by `0.0272`. Dense retrieval alone remains `0.0275` above BM25 hybrid
RRF and `0.1527` above the current PostgreSQL weighted pipeline. The weighted feature reranker
reduces BM25 RRF by `0.0981`, so its weights do not transfer to the stronger sparse branch.

These results identify fusion and reranking as the next measured bottleneck. Fusion parameters
must be selected on the SciFact train split or an internal IT support development set, then
reported once on the held-out test set. The test result must not be used to tune weights.

## Train-selected weighted RRF

The fixed grid was evaluated on all 809 SciFact train queries. It selected dense `1.0`, BM25
`0.25`, and exact `0.0` by nDCG@10. That configuration was then locked and evaluated once on
all 300 official test queries:

| Test variant | nDCG@10 | MAP@10 | Recall@5 | Recall@10 | MRR@10 |
|---|---:|---:|---:|---:|---:|
| Dense only | 0.7111 | 0.6612 | 0.7663 | 0.8526 | 0.6736 |
| BM25 RRF, equal weights | 0.6837 | 0.6359 | 0.7592 | 0.8177 | 0.6473 |
| **Train-selected BM25 weighted RRF** | **0.7318** | **0.6863** | **0.7897** | **0.8569** | **0.7003** |
| Previous PostgreSQL weighted runtime | 0.5584 | 0.5052 | 0.6306 | 0.7128 | 0.5134 |

Against dense-only, the locked fusion improves nDCG@10 by `0.0207`, MAP@10 by `0.0250`, and
MRR@10 by `0.0267`. A paired bootstrap over test queries with 10,000 resamples gives 95%
confidence intervals of `[0.0049, 0.0373]`, `[0.0063, 0.0449]`, and `[0.0075, 0.0461]`
respectively. Recall@10 changes by only `0.0043`, with an interval spanning zero, so the result
supports better ordering rather than a clear recall gain over dense-only.

Against the previous PostgreSQL weighted runtime, nDCG@10 improves by `0.1734` with a 95%
confidence interval of `[0.1322, 0.2154]`. The runtime therefore uses ACL-scoped BM25,
train-selected weighted RRF, and normalized fusion-score ordering. The internal IT regression
keeps Recall@5 at `1.0`, no-answer accuracy at `1.0`, and scope leakage at `0.0`; its evidence
threshold sweep selects `0.50`. SciFact remains an external scientific retrieval benchmark and
does not by itself establish IT support answer quality.

An internal ablation with exact weight `0.25` kept Recall@5 unchanged and reduced nDCG@5 from
`0.9351` to `0.9247`. The runtime therefore retains the train-selected exact weight `0.0`;
exact tokens are still preserved in query analysis and available to the BM25 branch.

## Candidate and ranking ablation

The full fake-embedding run isolates the retrieval branches without another paid API call.
The BM25 rows use the same production chunks, ACL/current-version SQL scope, and document
diversity policy as the runtime implementation:

| Variant | nDCG@10 | Recall@10 | MRR@10 |
|---|---:|---:|---:|
| Dense hash only | 0.3471 | 0.4375 | 0.3235 |
| PostgreSQL FTS only | 0.2723 | 0.3997 | 0.2355 |
| Runtime BM25 only | **0.6795** | **0.8030** | **0.6452** |
| PostgreSQL hybrid RRF | 0.4880 | 0.6150 | 0.4573 |
| PostgreSQL hybrid weighted | 0.5147 | 0.6586 | 0.4749 |
| BM25 hybrid RRF | 0.5758 | 0.7186 | 0.5409 |
| BM25 hybrid weighted | 0.5331 | 0.6869 | 0.4891 |

The weighted reranker improves RRF by `0.0267` nDCG@10. PostgreSQL FTS trails the verified
whole-document BM25 anchor by `0.4039`, identifying lexical candidate quality as the main
measured bottleneck. Runtime BM25 is within `0.0006` of the independently published Anserini
anchor and improves nDCG@10 by `0.4071` over PostgreSQL FTS on this split.

The fake dense branch pulls both BM25 hybrid variants below BM25 alone. It remains useful as a
deterministic regression baseline, while the production embedding ablation above is the source
for model-backed comparisons. BM25 and train-selected weighted RRF are now the runtime defaults
after the held-out and internal regression checks above. PostgreSQL FTS and the heuristic
weighted reranker remain available as explicit fallback configurations.

## Chunking isolation

| BM25 granularity | Indexed units | nDCG@10 | Recall@10 |
|---|---:|---:|---:|
| Whole document | 5,183 | 0.676188 | 0.8013 |
| Production chunks (`500/60`) | 5,263 | 0.676131 | 0.8013 |

Holding tokenization and BM25 scoring constant, production chunking changes nDCG@10 by only
`-0.000057` and leaves Recall@10 unchanged. Chunking is therefore not the measured cause of the
hybrid gap on SciFact. The runtime BM25 experiment confirms that replacing PostgreSQL
`ts_rank_cd` materially improves lexical candidates. The production embedding train/test
evaluation above supplies the selected hybrid fusion policy.

Detailed provenance, configuration, per-query rankings, relevance labels, metrics, and latency
are recorded in `fake-test-retrieval.json`, `openai-test-retrieval.json`, and
`bm25-test-retrieval.json`. Candidate-level ablations are in `fake-test-ablation.json`,
`fake-test-ablation-bm25.json`, and `openai-test-ablation-bm25.json`; the controlled chunking
run is in `bm25-chunked-test-retrieval.json`. Train-split fusion selection is recorded in
`openai-train-fusion-tuning.json`.

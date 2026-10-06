# Public retrieval benchmarks

This layer evaluates the application's real `HybridRetriever` against externally maintained
corpora, queries, and relevance judgments. It is separate from the internal IT support
regression suite under `evals/cases`.

## First supported dataset

`BEIR SciFact` is downloaded from the URL published by the BEIR project. The adapter verifies
the official MD5 checksum before extracting it. Downloaded archives and extracted data stay in
`.cache/public-benchmarks`, which is ignored by Git.

The Make targets run the evaluator in the backend container so it can reach the non-public
PostgreSQL service without exposing the database port on the host. They mount `HOST_CA_BUNDLE`
read-only for TLS verification on networks that use a company certificate authority.

Run a short integration smoke test:

```bash
make public-retrieval-smoke
```

Run the complete official test split with deterministic fake embeddings:

```bash
make public-retrieval-benchmark
```

Run the whole-document BM25 anchor:

```bash
make public-retrieval-bm25
```

Run dense, PostgreSQL FTS, RRF, and weighted reranker ablations in one shared index:

```bash
make public-retrieval-ablation-smoke
PUBLIC_RETRIEVAL_EMBEDDING_PROVIDER=openai \
RUN_PAID_PUBLIC_RETRIEVAL_BENCHMARK=true \
make public-retrieval-ablation
```

Run the complete split with the configured production OpenAI embedding model:

```bash
PUBLIC_RETRIEVAL_EMBEDDING_PROVIDER=openai \
RUN_PAID_PUBLIC_RETRIEVAL_BENCHMARK=true \
make public-retrieval-benchmark
```

Reports are written to `reports/public/scifact`. A report is comparable only when
`dataset.full_official_split` is `true`. Reports produced with `--query-limit` identify
themselves as smoke tests and must not be presented as benchmark results.

The report records dataset provenance, checksum, corpus and query counts, retrieval settings,
per-query results, `nDCG@10`, `MAP@10`, `Recall@5`, `Recall@10`, `Precision@10`, `MRR@10`, and
latency. Dataset licensing remains governed by the original dataset owner; see the recorded
homepage and license note before redistribution.

# Phase 5.2 cross-encoder comparison

Phase 5.2 reranks the same bounded pool of 20 hybrid candidates with the multilingual
`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` model. The experiment used the quantized
`onnx/model_quint8_avx2.onnx` CPU export. Weighted feature reranking remains the default.

Both runs used the same 42 cases, corpus snapshot, fake embedding provider, candidate limits,
document diversity rule, context expansion, citation selection, and PostgreSQL setup.

| Metric | Phase 5.1 weighted | Phase 5.2 cross encoder | Delta |
|---|---:|---:|---:|
| Recall@5 | 1.000 | 1.000 | +0.000 |
| Precision@5 | 0.219 | 0.219 | +0.000 |
| MRR@5 | 0.952 | 0.919 | -0.032 |
| nDCG@5 | 0.954 | 0.935 | -0.019 |
| Duplicate rate@5 | 0.000 | 0.000 | +0.000 |
| Expected document citation rate | 0.710 | 0.710 | +0.000 |
| Expected chunk recall@5 | 0.935 | 0.968 | +0.032 |
| Expected chunk citation rate | 0.677 | 0.677 | +0.000 |
| Citation precision | 0.677 | 0.677 | +0.000 |
| Scope leakage | 0.000 | 0.000 | +0.000 |

The cross encoder completed all 42 attempts without fallback. Its measured p95 duration was
581 ms per query. Mean duration after excluding the first model download and initialization
was 530 ms; the first attempt took 100.5 seconds.

The model found one additional expected chunk, but this did not improve citation selection and
it reduced rank quality. One case moved from rank 2 to rank 1, while three cases moved from rank
1 to rank 2. Keep weighted feature reranking as the production default. Retain the cross encoder
behind `RETRIEVAL_RERANKER=cross_encoder` for future experiments on a larger, human-labeled
holdout set.

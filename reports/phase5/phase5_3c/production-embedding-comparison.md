# Phase 5.3C — Production embedding benchmark

Both runs use chunking `500/60`, the weighted reranker, merged evidence scoring, and evidence
threshold `0.45`. The production run uses OpenAI `text-embedding-3-small` at 1536 dimensions.

| Metric | Fake embedding | Production embedding | Change |
|---|---:|---:|---:|
| Recall@5 | 1.0000 | 1.0000 | 0.0000 |
| Precision@5 | 0.2194 | 0.2194 | 0.0000 |
| MRR@5 | 0.9516 | 0.9462 | -0.0054 |
| nDCG@5 | 0.9542 | 0.9500 | -0.0042 |
| Expected chunk recall@5 | 0.9677 | 1.0000 | +0.0323 |
| Expected chunk citation rate | 0.7097 | 0.7742 | +0.0645 |
| Citation precision | 0.7586 | 0.7273 | -0.0313 |
| No-answer accuracy | 1.0000 | 1.0000 | 0.0000 |
| Scope leakage | 0.0000 | 0.0000 | 0.0000 |

Production embeddings retrieve all 31 expected chunks, including the previous fake-embedding
miss `ret-022`. They also select two additional expected chunks as citations while preserving
perfect no-answer accuracy and zero scope leakage. The tradeoff is a small decline in document
rank metrics and citation precision because the `0.45` threshold admits four additional
answerable citations, of which two match the exact chunk labels.

## Score separation

| Primary signal median | Fake positive | Fake negative | Production positive | Production negative |
|---|---:|---:|---:|---:|
| Vector similarity | 0.3518 | 0.1205 | 0.6001 | 0.3399 |
| Rerank score | 0.6476 | 0.2539 | 0.6520 | 0.2651 |
| Evidence score | 0.6354 | 0.1769 | 0.6560 | 0.2189 |

The automatic threshold sweep recommends `0.45` for both embedding providers. At that threshold,
both runs retain no-answer accuracy `1.0` and scope leakage `0.0`.

# Phase 4 query intelligence verification

Phase 4 resolves the current request before either agent runtime selects an action. The
resolved `QuerySpec` is shared with request policy and retrieval, so a low-confidence request
uses at most one model query-analysis call and retrieval does not analyze it again.

## Retrieval benchmark

The deterministic benchmark ran against a freshly migrated, isolated PostgreSQL database with
the same 22 development cases, fake embedding provider, corpus manifest, and retrieval limits as
Phase 3.

| Metric | Phase 3 | Phase 4 | Delta |
|---|---:|---:|---:|
| Recall@5 | 1.000 | 1.000 | +0.000 |
| Precision@5 | 0.215 | 0.215 | +0.000 |
| MRR@5 | 0.923 | 0.923 | +0.000 |
| nDCG@5 | 0.943 | 0.943 | +0.000 |
| Duplicate rate@5 | 0.382 | 0.373 | -0.009 |
| No-answer accuracy | 1.000 | 1.000 | +0.000 |
| Scope leakage | 0.000 | 0.000 | +0.000 |

The Recall@5 release gate remains satisfied. Detailed output is recorded in
`reports/phase4/retrieval-baseline.json` and `reports/phase4/retrieval-baseline.md`.

## Query-analysis policy verification

- Deterministic analysis runs first.
- High-confidence requests make zero model-analysis calls.
- Low-confidence requests make at most one model-analysis call.
- A model result below the acceptance threshold cannot expand tool permissions.
- Provider failure falls back to deterministic analysis.
- Exact terms from the current request remain in the semantic query.
- LangGraph, OpenAI Agents, request policy, and retrieval receive the same resolved analysis.
- Retrieval preserves the current raw query for sparse search and does not repeat model analysis.

These invariants are covered by the backend unit suite. The suite completed with 147 passing
tests, Ruff passed, and Mypy reported no issues in 139 application source files.

## Limits

The retrieval benchmark uses fake embeddings and does not call a paid query-analysis model. It
measures deterministic retrieval behavior and regression safety. Live model latency and monetary
cost remain provider and deployment dependent; the runtime records analyzer calls and tokens in
the run counters and usage ledger for production measurement.

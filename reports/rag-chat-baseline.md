# RAG chat baseline — 2026-09-16

## Scope

Deterministic fake-provider system test for the WP-06 wiring. This is not a semantic
quality claim and does not replace opt-in live evaluation.

## Results

| Scenario | Passed | Denominator | Evidence |
|---|---:|---:|---|
| Answer from authorized current document | 1 | 1 | Assistant message contains one server-owned source. |
| Insufficient evidence | 1 | 1 | Outcome is `no_answer` and sources are empty. |
| Cross-source citation validation | 1 | 1 | Provider contract rejects IDs outside retrieved evidence. |
| Bounded graph | 1 | 1 | Model/retrieval counters and recursion cap are enforced. |

Functional baseline: **4/4**. Semantic correctness remains an opt-in OpenAI evaluation
for WP-13; fake mode only proves API → queue contract → graph → retrieval → persisted
message/citation behavior.

# Phase 0 memory/context baseline

Generated: `2026-10-07T04:23:20.848537+00:00`

Dataset: `evals/memory_context/cases-v1.jsonl` (`c65ef94cc4b25984c74b1eb98ceae22c6302c569ad16d3d3cd76f3bdb3930def`)

Cases: **12** · paid model calls: **0**

## Aggregate metrics

| Metric | Result |
|---|---:|
| case_pass | 8/12 (66.7%) |
| confirmed_attempt_retention | 1/1 (100.0%) |
| critical_context_retention | 7/7 (100.0%) |
| current_request_preserved | 11/11 (100.0%) |
| expected_error | 1/1 (100.0%) |
| forbidden_context_exclusion | 1/6 (16.7%) |
| suggestion_not_confirmed | 1/1 (100.0%) |
| summarization_state | 11/11 (100.0%) |
| token_budget_compliance | 11/11 (100.0%) |
| truncation_state | 10/10 (100.0%) |
| unexpected_error | 11/11 (100.0%) |

## Cases

| Case | Category | Pass | Failed checks |
|---|---|---:|---|
| ctx-001 | latest_request | no | forbidden_context_exclusion |
| ctx-002 | follow_up | yes | — |
| ctx-003 | exact_token | yes | — |
| ctx-004 | attempt_state | yes | — |
| ctx-005 | attempt_state | yes | — |
| ctx-006 | memory_selection | no | forbidden_context_exclusion |
| ctx-007 | token_budget | yes | — |
| ctx-008 | compaction | yes | — |
| ctx-009 | prompt_injection | no | forbidden_context_exclusion |
| ctx-010 | token_budget | yes | — |
| ctx-011 | input_guard | yes | — |
| ctx-012 | memory_selection | no | forbidden_context_exclusion |

## Interpretation

Failures are frozen evidence for Phase 1/2 design work. They must not be removed from the dataset to improve the score; improvements must change the implementation or add a new versioned benchmark.

## Limitations

- This baseline evaluates the existing history builder, not the proposed ContextManager.
- It does not execute an LLM, tools, RAG, database authorization, or side effects.
- A failing gold expectation records an architectural gap and does not make the runner fail.

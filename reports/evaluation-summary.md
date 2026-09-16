# Product quality report — G-01 to G-09

Generated from commit `647c5c77f627f18af071bc90ae6a7593768ec524-dirty`. Release decision: **not_ready**.

| Gate | Status | Measurement |
|---|---|---|
| G-01 · authorization | pass | passed_tests=8, denominator=8, failed=0 |
| G-02 · side effects | pass | passed_tests=3, denominator=3, failed=0 |
| G-03 · duplicate/recovery | pass | passed_tests=3, denominator=3, failed=0 |
| G-04 · retrieval | pass | numerator=9, denominator=9, value=1.0 |
| G-05 · citations | not_measured | valid_source_ids=15, source_id_denominator=15, human_reviewed_claims=0 |
| G-06 · answerability | not_measured | fake_contract_pass=5, fake_contract_denominator=5 |
| G-07 · task success | not_measured | Non-RAG eval cases currently use scripted service contracts. |
| G-08 · memory | not_measured | safety_suite=pass, scripted_agent_accuracy_denominator=0 |
| G-09 · performance | not_measured | local_fake_p95_ms=14.962, concurrency=3 |

## Interpretation

`not_measured` is intentional: fake-provider contract checks do not establish live model quality or full-stack latency. Thresholds were not changed after seeing results.

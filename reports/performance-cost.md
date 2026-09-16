# Performance and cost measurement

## Local load probe

- Workload: in-process LangGraph RAG with deterministic fake provider
- Requests: 30 in 10 batches at concurrency 3
- P50/P95/max active latency: 10.979 / 14.962 / 16.97 ms
- Failures: 0
- This is an in-process deterministic probe, so it does **not** qualify for G-09.

## Cost

- Mode/model: fake / `deterministic-contract-v1`
- Tokens: 0 input, 0 output
- Calculated cost: USD 0.000000 (non_billable_fake)
- A fake run demonstrates accounting shape only; it is not a live cost claim.

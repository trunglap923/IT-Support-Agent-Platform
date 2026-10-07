# Memory/context evaluation cases

`cases-v1.jsonl` is the frozen Phase 0 scenario set for the current context builder. Each line
conforms to `context-baseline-case-v1.schema.json` and has an explicit observable expectation.

Run the baseline from the repository root:

```bash
make memory-context-baseline
```

The runner is deterministic, performs no paid model calls and does not require PostgreSQL or
Redis. A failed case records an architecture gap and does not make the process fail. Do not remove
or weaken a failing case to improve the score. Change behavior in a later phase, or create a new
versioned case set when the product contract changes.

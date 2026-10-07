# Memory and context contracts

These JSON Schemas are generated from the provider-neutral Pydantic contracts used to define the
memory and context architecture boundary. They document Phase 0 interfaces; they are not database
schemas and do not enable serving behavior by themselves.

Phase 1 adds the `tool-observation-v1` projection used to persist bounded tool outcomes without
copying raw tool payloads into working-memory snapshots.

Regenerate them from the repository root:

```bash
make export-memory-context-contracts
```

Contract versions are immutable. A breaking shape change requires a new schema version and a new
file; compatible implementation detail changes may keep the current version.

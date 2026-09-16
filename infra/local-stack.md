# Complete local application stack

`compose.yaml` defines exactly seven long-running services:

- `frontend`: non-root Nginx serving the React SPA on loopback port 5173.
- `api`: FastAPI on loopback port 8000 with PostgreSQL/Redis readiness checks.
- `worker-agent`: Celery agent queue, concurrency 2 by default.
- `worker-background`: Celery maintenance queue, concurrency 1 by default.
- `scheduler`: the single Celery beat process.
- `postgres`: PostgreSQL 17 + pgvector on the private backend network.
- `redis`: AOF/noeviction broker on the private backend network.

Only frontend and API publish host ports. PostgreSQL and Redis have no host/public binding in
the complete stack. Migration and seed commands run as explicit one-shot containers on the
private network; application startup never resets or migrates data implicitly.

Named volumes preserve PostgreSQL, Redis AOF and uploaded documents across `compose down`.
Removing volumes is deliberately not part of the normal stop workflow.

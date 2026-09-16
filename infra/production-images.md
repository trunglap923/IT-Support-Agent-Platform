# Production application images

Both application images use immutable base-image digests and a non-root runtime user.

```bash
docker build --file backend/Dockerfile --tag it-support-agent-api:local .
docker build --file frontend/Dockerfile --tag it-support-agent-web:local .
```

The backend exposes port 8000 and checks `/api/v1/health/live`. The frontend exposes port
8080, checks `/healthz`, serves the SPA, and proxies `/api/` (including SSE) to the Compose
service name `api`. Database migrations are a separate one-shot command; image startup never
changes schema automatically.

Runtime configuration and secrets must be injected as environment variables or secrets, not
baked into either image. The frontend image contains no `.env` file or backend credential.

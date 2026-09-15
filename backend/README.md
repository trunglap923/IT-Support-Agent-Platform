# Backend

FastAPI foundation for the IT Support Agent Platform.

From the repository root:

~~~bash
make backend-sync
make backend-check
make dev-backend
~~~

The default AI_PROVIDER=fake mode is offline and does not require an API key.
Set AI_PROVIDER=openai and OPENAI_API_KEY only for an explicit live smoke test.
No live model request is part of the default tests.

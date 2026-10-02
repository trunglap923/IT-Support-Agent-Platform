# Backend

FastAPI foundation for the IT Support Agent Platform.

From the repository root:

~~~bash
make backend-sync
make backend-check
make dev-backend
~~~

The default `TEXT_PROVIDER=fake` and `EMBEDDING_PROVIDER=fake` mode is offline and does not
require an API key. Set either provider to `openai` with `OPENAI_API_KEY` only for an explicit
live smoke test.
No live model request is part of the default tests.

`AGENT_RUNTIME=auto` selects the OpenAI Agents SDK orchestrator when `TEXT_PROVIDER=openai` and
keeps LangGraph in fake mode. Set `AGENT_RUNTIME=langgraph` for rollback. Apply database migrations
before enabling `AGENT_RUNTIME=openai_agents`, because approval resume uses
`agent_runtime_states`.

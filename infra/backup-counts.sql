SELECT json_build_object(
    'alembic_version', (SELECT version_num FROM alembic_version LIMIT 1),
    'users', (SELECT count(*) FROM users),
    'documents', (SELECT count(*) FROM documents),
    'document_versions', (SELECT count(*) FROM document_versions),
    'document_chunks', (SELECT count(*) FROM document_chunks),
    'conversations', (SELECT count(*) FROM conversations),
    'messages', (SELECT count(*) FROM messages),
    'tickets', (SELECT count(*) FROM tickets),
    'ticket_events', (SELECT count(*) FROM ticket_events),
    'memory_facts', (SELECT count(*) FROM memory_facts)
)::text;

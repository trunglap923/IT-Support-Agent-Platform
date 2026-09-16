"""Manage LangGraph PostgreSQL checkpoint tables through Alembic.

Revision ID: 0013_langgraph_checkpoints
Revises: 0012_approval_lifecycle
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0013_langgraph_checkpoints"
down_revision: str | None = "0012_approval_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE checkpoint_migrations (
            v INTEGER PRIMARY KEY
        );
        CREATE TABLE checkpoints (
            thread_id TEXT NOT NULL,
            checkpoint_ns TEXT NOT NULL DEFAULT '',
            checkpoint_id TEXT NOT NULL,
            parent_checkpoint_id TEXT,
            type TEXT,
            checkpoint JSONB NOT NULL,
            metadata JSONB NOT NULL DEFAULT '{}',
            PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
        );
        CREATE TABLE checkpoint_blobs (
            thread_id TEXT NOT NULL,
            checkpoint_ns TEXT NOT NULL DEFAULT '',
            channel TEXT NOT NULL,
            version TEXT NOT NULL,
            type TEXT NOT NULL,
            blob BYTEA,
            PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
        );
        CREATE TABLE checkpoint_writes (
            thread_id TEXT NOT NULL,
            checkpoint_ns TEXT NOT NULL DEFAULT '',
            checkpoint_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            task_path TEXT NOT NULL DEFAULT '',
            idx INTEGER NOT NULL,
            channel TEXT NOT NULL,
            type TEXT,
            blob BYTEA NOT NULL,
            PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
        );
        CREATE INDEX checkpoints_thread_id_idx ON checkpoints(thread_id);
        CREATE INDEX checkpoint_blobs_thread_id_idx ON checkpoint_blobs(thread_id);
        CREATE INDEX checkpoint_writes_thread_id_idx ON checkpoint_writes(thread_id);
        INSERT INTO checkpoint_migrations(v) SELECT generate_series(0, 9);
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE checkpoint_writes;
        DROP TABLE checkpoint_blobs;
        DROP TABLE checkpoints;
        DROP TABLE checkpoint_migrations;
        """
    )

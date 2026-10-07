"""Add auditable semantic assertions and consolidated incident episodes.

Revision ID: 0023_semantic_episodic_memory
Revises: 0022_active_context_manager
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import VECTOR
from sqlalchemy.dialects import postgresql

revision: str = "0023_semantic_episodic_memory"
down_revision: str | None = "0022_active_context_manager"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    json_object = sa.text("'{}'::jsonb")
    json_array = sa.text("'[]'::jsonb")
    op.create_table(
        "memory_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(24), nullable=False),
        sa.Column("source_ref", sa.String(500), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("safe_excerpt", sa.String(500), nullable=True),
        sa.Column("authority_tier", sa.Integer(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("ticket_id", sa.Uuid(), nullable=True),
        sa.Column("safe_metadata", postgresql.JSONB(), server_default=json_object, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "source_type IN ('cmdb','idp','mdm','tool','user_confirmed','ticket','ai_inferred')",
            name="memory_source_type_allowlist",
        ),
        sa.CheckConstraint(
            "authority_tier BETWEEN 0 AND 100", name="memory_source_authority_range"
        ),
        sa.CheckConstraint("length(content_hash) = 64", name="memory_source_hash_length"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_id",
            "source_type",
            "source_ref",
            "content_hash",
            name="uq_memory_source_identity",
        ),
    )
    for name in ("owner_id", "message_id", "run_id", "ticket_id"):
        op.create_index(f"ix_memory_sources_{name}", "memory_sources", [name])

    op.create_table(
        "memory_assertions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("subject_type", sa.String(20), nullable=False),
        sa.Column("subject_id", sa.String(160), nullable=False),
        sa.Column("predicate", sa.String(120), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("normalized_text", sa.String(1000), nullable=False),
        sa.Column("value_hash", sa.String(64), nullable=False),
        sa.Column("scope", sa.String(20), server_default="global", nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("authority_tier", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("supersedes_id", sa.Uuid(), nullable=True),
        sa.Column("compatibility_fact_id", sa.Uuid(), nullable=True),
        sa.Column("embedding", VECTOR(1536), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "subject_type IN ('user','device','account','service')",
            name="memory_assertion_subject_type_allowlist",
        ),
        sa.CheckConstraint(
            "status IN ('active','superseded','deleted','quarantined','conflicted')",
            name="memory_assertion_status_allowlist",
        ),
        sa.CheckConstraint("scope IN ('global','device')", name="memory_assertion_scope_allowlist"),
        sa.CheckConstraint(
            "(scope = 'device') = (device_id IS NOT NULL)",
            name="memory_assertion_device_scope_matches",
        ),
        sa.CheckConstraint(
            "authority_tier BETWEEN 0 AND 100", name="memory_assertion_authority_range"
        ),
        sa.CheckConstraint("confidence BETWEEN 0 AND 1", name="memory_assertion_confidence_range"),
        sa.CheckConstraint("length(value_hash) = 64", name="memory_assertion_hash_length"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["memory_sources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supersedes_id"], ["memory_assertions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["compatibility_fact_id"], ["memory_facts.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for name in ("owner_id", "source_id", "device_id", "supersedes_id", "compatibility_fact_id"):
        op.create_index(f"ix_memory_assertions_{name}", "memory_assertions", [name])
    op.create_index(
        "ix_memory_assertions_owner_status_updated",
        "memory_assertions",
        ["owner_id", "status", "updated_at"],
    )
    op.create_index(
        "uq_memory_assertion_active_claim",
        "memory_assertions",
        ["owner_id", "subject_type", "subject_id", "predicate"],
        unique=True,
        postgresql_where=sa.text("status = 'active' AND deleted_at IS NULL"),
    )

    op.create_table(
        "memory_conflicts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("subject_type", sa.String(20), nullable=False),
        sa.Column("subject_id", sa.String(160), nullable=False),
        sa.Column("predicate", sa.String(120), nullable=False),
        sa.Column("assertion_a_id", sa.Uuid(), nullable=False),
        sa.Column("assertion_b_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("resolution", sa.String(40), nullable=True),
        sa.Column("selected_assertion_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('pending','resolved','quarantined')",
            name="memory_conflict_status_allowlist",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assertion_a_id"], ["memory_assertions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assertion_b_id"], ["memory_assertions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["selected_assertion_id"], ["memory_assertions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "assertion_a_id", "assertion_b_id", name="uq_memory_conflict_assertion_pair"
        ),
    )
    for name in ("owner_id", "assertion_a_id", "assertion_b_id"):
        op.create_index(f"ix_memory_conflicts_{name}", "memory_conflicts", [name])
    op.create_index(
        "ix_memory_conflicts_owner_status", "memory_conflicts", ["owner_id", "status", "created_at"]
    )

    op.create_table(
        "memory_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("proposal_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column("operation", sa.String(12), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("decided_by_type", sa.String(20), nullable=False),
        sa.Column("decided_by_id", sa.Uuid(), nullable=True),
        sa.Column("policy_version", sa.String(80), nullable=False),
        sa.Column("reason_code", sa.String(80), nullable=False),
        sa.Column("target_assertion_id", sa.Uuid(), nullable=True),
        sa.Column("resulting_assertion_id", sa.Uuid(), nullable=True),
        sa.Column("source_ids", postgresql.JSONB(), server_default=json_array, nullable=False),
        sa.Column("correlation_id", sa.String(180), nullable=False),
        sa.Column("safe_metadata", postgresql.JSONB(), server_default=json_object, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "operation IN ('add','update','delete','noop')",
            name="memory_decision_operation_allowlist",
        ),
        sa.CheckConstraint(
            "status IN ('accepted','rejected','quarantined')",
            name="memory_decision_status_allowlist",
        ),
        sa.CheckConstraint(
            "decided_by_type IN ('system','user','it_reviewer','connector')",
            name="memory_decision_actor_type_allowlist",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["decided_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["target_assertion_id"], ["memory_assertions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["resulting_assertion_id"], ["memory_assertions.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    for name in (
        "owner_id",
        "run_id",
        "target_assertion_id",
        "resulting_assertion_id",
        "correlation_id",
    ):
        op.create_index(f"ix_memory_decisions_{name}", "memory_decisions", [name])
    op.create_index(
        "ix_memory_decisions_owner_created", "memory_decisions", ["owner_id", "created_at"]
    )

    op.create_table(
        "incident_episodes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=True),
        sa.Column("ticket_id", sa.Uuid(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("verified", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("service_ids", postgresql.JSONB(), server_default=json_array, nullable=False),
        sa.Column("error_codes", postgresql.JSONB(), server_default=json_array, nullable=False),
        sa.Column("source_refs", postgresql.JSONB(), server_default=json_array, nullable=False),
        sa.Column(
            "verification_refs", postgresql.JSONB(), server_default=json_array, nullable=False
        ),
        sa.Column("embedding", VECTOR(1536), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "outcome IN ('resolved','unresolved','ticket_created','cancelled')",
            name="incident_episode_outcome_allowlist",
        ),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for name in ("run_id", "owner_id", "conversation_id", "device_id", "ticket_id"):
        op.create_index(f"ix_incident_episodes_{name}", "incident_episodes", [name])
    op.create_index(
        "ix_incident_episodes_owner_completed", "incident_episodes", ["owner_id", "completed_at"]
    )
    op.create_index(
        "ix_incident_episodes_owner_device",
        "incident_episodes",
        ["owner_id", "device_id", "completed_at"],
    )

    op.create_table(
        "episode_actions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("action_kind", sa.String(24), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("summary", sa.String(1000), nullable=False),
        sa.Column("receipt_ref", sa.String(500), nullable=True),
        sa.Column("source_ref", sa.String(500), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("ordinal >= 0", name="episode_action_ordinal_non_negative"),
        sa.ForeignKeyConstraint(["episode_id"], ["incident_episodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("episode_id", "ordinal", name="uq_episode_action_ordinal"),
    )
    op.create_index("ix_episode_actions_episode_id", "episode_actions", ["episode_id"])

    # Existing confirmed facts remain API-compatible and become first-class assertions.
    op.execute(
        sa.text("""
        INSERT INTO memory_sources (id, owner_id, source_type, source_ref, content_hash,
          safe_excerpt, authority_tier, observed_at, message_id, run_id, safe_metadata)
        SELECT gen_random_uuid(), f.owner_id, 'user_confirmed',
          'legacy-memory-fact:' || f.id::text || '-v' || f.version::text,
          md5(f.key || '=' || f.value) || md5(reverse(f.key || '=' || f.value)),
          left(f.key || ': ' || f.value, 500), 80, f.updated_at, j.source_message_id,
          j.run_id, jsonb_build_object('backfilled', true)
        FROM memory_facts f
        JOIN memory_candidates c ON c.id = f.candidate_id
        JOIN memory_extraction_jobs j ON j.id = c.job_id
    """)
    )
    op.execute(
        sa.text("""
        INSERT INTO memory_assertions (id, owner_id, source_id, subject_type, subject_id,
          predicate, value, normalized_text, value_hash, scope, device_id, status,
          authority_tier, confidence, valid_from, valid_to, compatibility_fact_id,
          deleted_at)
        SELECT gen_random_uuid(), f.owner_id, s.id,
          CASE WHEN f.scope = 'device' THEN 'device' ELSE 'user' END,
          CASE WHEN f.scope = 'device' THEN f.device_id::text ELSE f.owner_id::text END,
          f.key, jsonb_build_object('value', f.value), left(f.key || ': ' || f.value, 1000),
          md5(jsonb_build_object('value', f.value)::text) ||
            md5(reverse(jsonb_build_object('value', f.value)::text)),
          f.scope, f.device_id, CASE WHEN f.deleted_at IS NULL THEN 'active' ELSE 'deleted' END,
          80, 1.0, f.created_at, f.deleted_at, f.id, f.deleted_at
        FROM memory_facts f
        JOIN memory_sources s ON s.owner_id = f.owner_id
          AND s.source_ref = 'legacy-memory-fact:' || f.id::text || '-v' || f.version::text
    """)
    )
    op.execute(
        sa.text("""
        INSERT INTO memory_decisions (id, proposal_id, owner_id, run_id, operation, status,
          decided_by_type, decided_by_id, policy_version, reason_code,
          target_assertion_id, resulting_assertion_id, source_ids, correlation_id, safe_metadata)
        SELECT gen_random_uuid(), gen_random_uuid(), a.owner_id, s.run_id,
          CASE WHEN a.status = 'deleted' THEN 'delete' ELSE 'add' END, 'accepted',
          'system', NULL, 'memory-policy-v1', 'legacy_fact_backfill',
          CASE WHEN a.status = 'deleted' THEN a.id ELSE NULL END,
          CASE WHEN a.status = 'active' THEN a.id ELSE NULL END,
          jsonb_build_array(s.id::text), 'backfill:' || a.compatibility_fact_id::text,
          jsonb_build_object('backfilled', true)
        FROM memory_assertions a JOIN memory_sources s ON s.id = a.source_id
    """)
    )


def downgrade() -> None:
    op.drop_table("episode_actions")
    op.drop_table("incident_episodes")
    op.drop_table("memory_decisions")
    op.drop_table("memory_conflicts")
    op.drop_table("memory_assertions")
    op.drop_table("memory_sources")

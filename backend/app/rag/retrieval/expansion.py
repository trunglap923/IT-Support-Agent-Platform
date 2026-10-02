"""ACL-scoped neighboring and parent-section leaf expansion."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.principal import Principal
from app.db.models import Document, DocumentChunk, DocumentSection, DocumentVersion
from app.rag.retrieval.filters import readable_current_document
from app.rag.retrieval.models import RetrievalCandidate, RetrievalContextChunk
from app.rag.retrieval.store import candidate_from_row, scoped_chunk_query


async def expand_parent_and_neighbors(
    session: AsyncSession,
    candidates: list[RetrievalCandidate],
    *,
    principal: Principal,
    now: datetime,
    max_neighbors_per_seed: int = 2,
) -> list[RetrievalContextChunk]:
    """Add close leaf chunks, keeping every lookup under current document ACLs."""
    seeds = [item for item in candidates if item.section_id is not None]
    if not seeds:
        return []

    section_ids = {item.section_id for item in seeds if item.section_id is not None}
    parent_rows = (
        await session.execute(
            select(DocumentSection.id, DocumentSection.parent_id)
            .join(DocumentVersion, DocumentSection.version_id == DocumentVersion.id)
            .join(Document, DocumentVersion.document_id == Document.id)
            .where(
                DocumentSection.id.in_(section_ids),
                readable_current_document(principal, now=now),
            )
        )
    ).all()
    parent_by_section = {section_id: parent_id for section_id, parent_id in parent_rows}

    clauses = []
    parent_ids: set[UUID] = set()
    for seed in seeds:
        if seed.section_id is not None:
            parent_id = parent_by_section.get(seed.section_id)
            if parent_id is not None:
                parent_ids.add(parent_id)
        clauses.append(
            and_(
                DocumentChunk.version_id == seed.version_id,
                DocumentChunk.ordinal >= max(0, seed.ordinal - max_neighbors_per_seed),
                DocumentChunk.ordinal <= seed.ordinal + max_neighbors_per_seed,
            )
        )
    if parent_ids:
        clauses.append(
            and_(
                DocumentChunk.version_id.in_({item.version_id for item in seeds}),
                DocumentChunk.section_id.in_(parent_ids),
            )
        )

    rows = (
        await session.execute(
            scoped_chunk_query(principal, now=now)
            .where(or_(*clauses))
            .order_by(DocumentChunk.version_id, DocumentChunk.ordinal)
            .limit(max(1, len(seeds) * (max_neighbors_per_seed * 2 + 2)))
        )
    ).all()
    known_ids = {item.chunk_id for item in candidates}
    output: list[RetrievalContextChunk] = []
    for row in rows:
        candidate = candidate_from_row(row)
        if candidate.chunk_id not in known_ids:
            known_ids.add(candidate.chunk_id)
            output.append(
                RetrievalContextChunk(
                    candidate=candidate,
                    expansion_kind=(
                        "parent_section" if candidate.section_id in parent_ids else "neighbor"
                    ),
                )
            )
    return output

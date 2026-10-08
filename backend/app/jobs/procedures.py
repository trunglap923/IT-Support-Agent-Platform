"""Background compilation and source-validity monitoring for procedures."""

from __future__ import annotations

from app.db import Database
from app.procedures.compiler import ProcedureCompiler
from app.procedures.registry import ProcedureRegistryService


async def compile_procedure_candidates(database: Database) -> int:
    async with database.session() as session, session.begin():
        return await ProcedureCompiler().compile_verified_episodes(session)


async def count_stale_procedure_versions(database: Database) -> int:
    async with database.session() as session:
        return len(await ProcedureRegistryService().stale_versions(session))

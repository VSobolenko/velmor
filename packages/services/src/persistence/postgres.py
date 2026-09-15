from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.gate import GateDecision
from packages.services.src.persistence.schema import Schema


class PostgresStore:
    """Candidate and verdict storage in PostgreSQL.

    Satisfies both repository protocols; the two interfaces stay separate because
    the operations belong to different stages of the pipeline.

    ``pending_audit`` is an anti-join against the verdict table, so a candidate is
    re-examined only while it has no recorded outcome. That is what makes a run
    that paused for human review resumable: it has no verdict yet, so the next
    pass picks it up through the checkpointer instead of investigating again.
    """

    def __init__(
        self,
        engine: AsyncEngine,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._engine = engine
        self._session_factory = session_factory

    async def ensure_schema(self) -> None:
        """Create missing tables.

        A development convenience, not a migration strategy. Production schema
        changes belong in Alembic, which is why this only ever creates and never
        alters.
        """
        async with self._engine.begin() as connection:
            await connection.run_sync(Schema.metadata.create_all)

    async def upsert_many(self, candidates: tuple[Candidate, ...]) -> int:
        if not candidates:
            return 0

        statement = (
            insert(Schema.candidates)
            .values([self._row_for(candidate) for candidate in candidates])
            .on_conflict_do_nothing(index_elements=['id'])
            .returning(Schema.candidates.c.id)
        )
        async with self._session_factory() as session:
            result = await session.execute(statement)
            written = len(result.scalars().all())
            await session.commit()
        return written

    async def pending_audit(self, limit: int) -> tuple[Candidate, ...]:
        statement = (
            select(Schema.candidates)
            .outerjoin(
                Schema.rights_records,
                Schema.rights_records.c.candidate_id == Schema.candidates.c.id,
            )
            .where(Schema.rights_records.c.candidate_id.is_(None))
            .order_by(Schema.candidates.c.discovered_at, Schema.candidates.c.id)
            .limit(limit)
        )
        async with self._session_factory() as session:
            rows = (await session.execute(statement)).mappings().all()
        return tuple(self._candidate_from(row) for row in rows)

    async def save(self, decision: GateDecision) -> None:
        statement = (
            insert(Schema.rights_records)
            .values(
                candidate_id=decision.candidate_id,
                source_id=decision.record.source_id,
                license_id=decision.record.license_id,
                verdict=decision.record.verdict.value,
                publishable=decision.publishable,
                reason=' | '.join(decision.reasons) or decision.record.reason,
                record=decision.record.model_dump(mode='json'),
                decided_at=decision.record.decided_at,
            )
            .on_conflict_do_update(
                index_elements=['candidate_id'],
                set_={
                    'license_id': decision.record.license_id,
                    'verdict': decision.record.verdict.value,
                    'publishable': decision.publishable,
                    'reason': ' | '.join(decision.reasons) or decision.record.reason,
                    'record': decision.record.model_dump(mode='json'),
                    'decided_at': decision.record.decided_at,
                },
            )
        )
        async with self._session_factory() as session:
            await session.execute(statement)
            await session.commit()

    @staticmethod
    def _row_for(candidate: Candidate) -> dict:
        return {
            'id': candidate.id,
            'source_id': candidate.source_id,
            'title': candidate.title,
            'landing_url': candidate.landing_url,
            'creator': candidate.creator,
            'content_type': candidate.content_type,
            'declared_license_id': candidate.declared_license_id,
            'declared_license_text': candidate.declared_license_text,
            'download_url': candidate.download_url,
            'size_bytes': candidate.size_bytes,
        }

    @staticmethod
    def _candidate_from(row: object) -> Candidate:
        return Candidate(
            id=row['id'],
            source_id=row['source_id'],
            title=row['title'],
            landing_url=row['landing_url'],
            creator=row['creator'],
            content_type=row['content_type'],
            declared_license_id=row['declared_license_id'],
            declared_license_text=row['declared_license_text'],
            download_url=row['download_url'],
            size_bytes=row['size_bytes'],
        )

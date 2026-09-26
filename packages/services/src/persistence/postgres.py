from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from sqlalchemy import Select, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from packages.services.src.domain.account import Account, Session
from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.catalogue import (
    CatalogueEntry,
    CatalogueEntryState,
)
from packages.services.src.domain.catalogue_query import (
    CatalogueFilter,
    CatalogueMatches,
    CategoryGoodsCount,
)
from packages.services.src.domain.category import Category, CategoryName
from packages.services.src.domain.entitlement import Entitlement
from packages.services.src.domain.gate import GateDecision
from packages.services.src.domain.license import StorefrontListing
from packages.services.src.domain.order import Order
from packages.services.src.domain.presentation import CataloguePresentation, Locale
from packages.services.src.domain.preview import CatalogueCover
from packages.services.src.domain.rights import RightsRecord
from packages.services.src.domain.seller import SellerDisclosure
from packages.services.src.persistence.contract import SELLER_DISCLOSURE_KEY
from packages.services.src.persistence.schema import Schema


class PostgresStore:
    """Candidate, verdict, catalogue, category and commerce storage in PostgreSQL.

    Satisfies every repository protocol; the interfaces stay separate because the
    operations belong to different stages of the pipeline.

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

    async def by_candidate_id(self, candidate_id: str) -> Candidate | None:
        statement = select(Schema.candidates).where(Schema.candidates.c.id == candidate_id)
        async with self._session_factory() as session:
            row = (await session.execute(statement)).mappings().one_or_none()
        if row is None:
            return None
        return self._candidate_from(row)

    async def published(self, limit: int) -> tuple[tuple[Candidate, RightsRecord], ...]:
        """Publishable goods, most recently decided first.

        ``publishable`` is the gate's own column, so the storefront reads the
        verdict rather than re-deriving it. Only the record JSONB is selected
        beside the candidate: its scalar columns are duplicated in the record and
        an unlabelled join would collide on ``source_id``.
        """
        statement = (
            select(Schema.candidates, Schema.rights_records.c.record)
            .join(
                Schema.rights_records,
                Schema.rights_records.c.candidate_id == Schema.candidates.c.id,
            )
            .where(Schema.rights_records.c.publishable.is_(True))
            .order_by(Schema.rights_records.c.decided_at.desc(), Schema.candidates.c.id)
            .limit(limit)
        )
        async with self._session_factory() as session:
            rows = (await session.execute(statement)).mappings().all()
        return tuple(
            (self._candidate_from(row), RightsRecord.model_validate(row['record']))
            for row in rows
        )

    async def published_count(self) -> int:
        statement = (
            select(func.count())
            .select_from(Schema.candidates)
            .join(
                Schema.rights_records,
                Schema.rights_records.c.candidate_id == Schema.candidates.c.id,
            )
            .where(Schema.rights_records.c.publishable.is_(True))
        )
        async with self._session_factory() as session:
            return (await session.execute(statement)).scalar_one()

    async def search(self, query: CatalogueFilter) -> CatalogueMatches:
        """Every saleable match.

        No ``limit``: the ordering the caller wants is by the title resolved for
        a locale, which is not a column, so the rows have to reach the service
        before they can be ordered or paged. ``total`` is the length of that
        result for the same reason - the count cannot be taken before the text
        term is applied either.
        """
        conditions = [
            Schema.catalogue_entries.c.state == CatalogueEntryState.PUBLISHED.value,
            Schema.catalogue_entries.c.listing == StorefrontListing.PAID_OK.value,
        ]
        if query.category_id is not None:
            conditions.append(Schema.catalogue_entries.c.category_id == query.category_id)
        if query.license_id is not None:
            conditions.append(
                Schema.catalogue_entries.c.entry['license_id'].astext == query.license_id
            )
        statement = (
            select(Schema.catalogue_entries.c.entry)
            .where(*conditions)
            .order_by(
                Schema.catalogue_entries.c.published_at.desc(),
                Schema.catalogue_entries.c.candidate_id,
            )
        )
        async with self._session_factory() as session:
            rows = (await session.execute(statement)).mappings().all()
        entries = tuple(CatalogueEntry.model_validate(row['entry']) for row in rows)
        return CatalogueMatches(entries=entries, total=len(entries))

    async def counts_by_category(self) -> tuple[CategoryGoodsCount, ...]:
        statement = (
            select(
                Schema.catalogue_entries.c.category_id,
                func.count().label('goods'),
            )
            .where(
                Schema.catalogue_entries.c.state == CatalogueEntryState.PUBLISHED.value,
                Schema.catalogue_entries.c.listing == StorefrontListing.PAID_OK.value,
                Schema.catalogue_entries.c.category_id.is_not(None),
            )
            .group_by(Schema.catalogue_entries.c.category_id)
            .order_by(Schema.catalogue_entries.c.category_id)
        )
        async with self._session_factory() as session:
            rows = (await session.execute(statement)).mappings().all()
        return tuple(
            CategoryGoodsCount(category_id=row['category_id'], count=row['goods'])
            for row in rows
        )

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

    async def save_entry(self, entry: CatalogueEntry) -> None:
        statement = (
            insert(Schema.catalogue_entries)
            .values(
                candidate_id=entry.candidate_id,
                source_id=entry.source_id,
                category_id=entry.category_id,
                listing=entry.listing.value,
                state=entry.state.value,
                published_at=entry.published_at,
                entry=entry.model_dump(mode='json'),
            )
            .on_conflict_do_update(
                index_elements=['candidate_id'],
                set_={
                    'source_id': entry.source_id,
                    'category_id': entry.category_id,
                    'listing': entry.listing.value,
                    'state': entry.state.value,
                    'published_at': entry.published_at,
                    'entry': entry.model_dump(mode='json'),
                },
            )
        )
        async with self._session_factory() as session:
            await session.execute(statement)
            await session.commit()

    async def by_candidate(self, candidate_id: str) -> CatalogueEntry | None:
        statement = select(Schema.catalogue_entries.c.entry).where(
            Schema.catalogue_entries.c.candidate_id == candidate_id
        )
        async with self._session_factory() as session:
            row = (await session.execute(statement)).mappings().one_or_none()
        if row is None:
            return None
        return CatalogueEntry.model_validate(row['entry'])

    async def by_category(self, category_id: str) -> tuple[CatalogueEntry, ...]:
        statement = (
            select(Schema.catalogue_entries.c.entry)
            .where(Schema.catalogue_entries.c.category_id == category_id)
            .order_by(
                Schema.catalogue_entries.c.published_at.desc(),
                Schema.catalogue_entries.c.candidate_id,
            )
        )
        async with self._session_factory() as session:
            rows = (await session.execute(statement)).mappings().all()
        return tuple(CatalogueEntry.model_validate(row['entry']) for row in rows)

    async def entries(self, limit: int) -> tuple[CatalogueEntry, ...]:
        statement = (
            select(Schema.catalogue_entries.c.entry)
            .order_by(
                Schema.catalogue_entries.c.published_at.desc(),
                Schema.catalogue_entries.c.candidate_id,
            )
            .limit(limit)
        )
        async with self._session_factory() as session:
            rows = (await session.execute(statement)).mappings().all()
        return tuple(CatalogueEntry.model_validate(row['entry']) for row in rows)

    async def save_category(self, category: Category) -> None:
        """Upsert the category and replace its names in one transaction.

        The ``category`` JSONB column still receives the whole model, but it is
        no longer a read path: a row written before this change cannot carry the
        names, and ``Category.names`` has no default, so validation from JSONB
        would fail on every existing row. The scalar columns and the
        ``category_names`` table are what reads use.
        """
        statement = (
            insert(Schema.categories)
            .values(
                category_id=category.category_id,
                name=category.name,
                slug=category.slug,
                saleor_category_id=category.saleor_category_id,
                created_at=category.created_at,
                category=category.model_dump(mode='json'),
            )
            .on_conflict_do_update(
                index_elements=['category_id'],
                set_={
                    'name': category.name,
                    'slug': category.slug,
                    'saleor_category_id': category.saleor_category_id,
                    'created_at': category.created_at,
                    'category': category.model_dump(mode='json'),
                },
            )
        )
        async with self._session_factory() as session:
            await session.execute(statement)
            await session.execute(
                delete(Schema.category_names).where(
                    Schema.category_names.c.category_id == category.category_id
                )
            )
            if len(category.names) > 0:
                await session.execute(
                    insert(Schema.category_names).values(
                        [
                            {
                                'category_id': category.category_id,
                                'locale': name.locale.value,
                                'name': name.name,
                            }
                            for name in category.names
                        ]
                    )
                )
            await session.commit()

    async def by_id(self, category_id: str) -> Category | None:
        statement = (
            self._category_select()
            .where(Schema.categories.c.category_id == category_id)
            .order_by(Schema.category_names.c.locale)
        )
        async with self._session_factory() as session:
            rows = (await session.execute(statement)).mappings().all()
        if len(rows) == 0:
            return None
        return self._category_from(rows)

    async def by_slug(self, slug: str) -> Category | None:
        statement = (
            self._category_select()
            .where(Schema.categories.c.slug == slug)
            .order_by(Schema.category_names.c.locale)
        )
        async with self._session_factory() as session:
            rows = (await session.execute(statement)).mappings().all()
        if len(rows) == 0:
            return None
        return self._category_from(rows)

    async def all(self) -> tuple[Category, ...]:
        """Every category from one statement, names included.

        A read per category would make listing the taxonomy cost one query per
        row, so the names are joined for the whole list. The order is the scalar
        ``name`` then ``category_id`` then the locale, so it does not move with
        the language a buyer reads.
        """
        statement = self._category_select().order_by(
            Schema.categories.c.name,
            Schema.categories.c.category_id,
            Schema.category_names.c.locale,
        )
        async with self._session_factory() as session:
            rows = (await session.execute(statement)).mappings().all()
        return self._categories_from(rows)

    async def delete_category(self, category_id: str) -> None:
        async with self._session_factory() as session:
            await session.execute(
                delete(Schema.category_names).where(
                    Schema.category_names.c.category_id == category_id
                )
            )
            await session.execute(
                delete(Schema.categories).where(
                    Schema.categories.c.category_id == category_id
                )
            )
            await session.commit()

    async def save_presentation(self, presentation: CataloguePresentation) -> None:
        statement = (
            insert(Schema.catalogue_presentations)
            .values(
                candidate_id=presentation.candidate_id,
                locale=presentation.locale.value,
                title=presentation.title,
                source=presentation.source.value,
                updated_at=presentation.updated_at,
                presentation=presentation.model_dump(mode='json'),
            )
            .on_conflict_do_update(
                index_elements=['candidate_id', 'locale'],
                set_={
                    'title': presentation.title,
                    'source': presentation.source.value,
                    'updated_at': presentation.updated_at,
                    'presentation': presentation.model_dump(mode='json'),
                },
            )
        )
        async with self._session_factory() as session:
            await session.execute(statement)
            await session.commit()

    async def presentations_for(
        self, candidate_id: str
    ) -> tuple[CataloguePresentation, ...]:
        statement = (
            select(Schema.catalogue_presentations.c.presentation)
            .where(Schema.catalogue_presentations.c.candidate_id == candidate_id)
            .order_by(Schema.catalogue_presentations.c.locale)
        )
        async with self._session_factory() as session:
            rows = (await session.execute(statement)).mappings().all()
        return tuple(
            CataloguePresentation.model_validate(row['presentation']) for row in rows
        )

    async def all_presentations(self) -> tuple[CataloguePresentation, ...]:
        statement = select(Schema.catalogue_presentations.c.presentation).order_by(
            Schema.catalogue_presentations.c.candidate_id,
            Schema.catalogue_presentations.c.locale,
        )
        async with self._session_factory() as session:
            rows = (await session.execute(statement)).mappings().all()
        return tuple(
            CataloguePresentation.model_validate(row['presentation']) for row in rows
        )

    async def save_cover(self, cover: CatalogueCover) -> None:
        statement = (
            insert(Schema.catalogue_covers)
            .values(
                candidate_id=cover.candidate_id,
                source=cover.source.value,
                attached_at=cover.attached_at,
                cover=cover.model_dump(mode='json'),
            )
            .on_conflict_do_update(
                index_elements=['candidate_id'],
                set_={
                    'source': cover.source.value,
                    'attached_at': cover.attached_at,
                    'cover': cover.model_dump(mode='json'),
                },
            )
        )
        async with self._session_factory() as session:
            await session.execute(statement)
            await session.commit()

    async def cover_for(self, candidate_id: str) -> CatalogueCover | None:
        statement = select(Schema.catalogue_covers.c.cover).where(
            Schema.catalogue_covers.c.candidate_id == candidate_id
        )
        async with self._session_factory() as session:
            row = (await session.execute(statement)).mappings().one_or_none()
        if row is None:
            return None
        return CatalogueCover.model_validate(row['cover'])

    async def all_covers(self) -> tuple[CatalogueCover, ...]:
        statement = select(Schema.catalogue_covers.c.cover).order_by(
            Schema.catalogue_covers.c.candidate_id
        )
        async with self._session_factory() as session:
            rows = (await session.execute(statement)).mappings().all()
        return tuple(CatalogueCover.model_validate(row['cover']) for row in rows)

    async def save_entitlement(self, entitlement: Entitlement) -> None:
        statement = (
            insert(Schema.entitlements)
            .values(
                order_id=entitlement.order_id,
                candidate_id=entitlement.candidate_id,
                buyer_id=entitlement.buyer_id,
                state=entitlement.state.value,
                granted_at=entitlement.granted_at,
                entitlement=entitlement.model_dump(mode='json'),
            )
            .on_conflict_do_update(
                index_elements=['order_id', 'candidate_id'],
                set_={
                    'buyer_id': entitlement.buyer_id,
                    'state': entitlement.state.value,
                    'granted_at': entitlement.granted_at,
                    'entitlement': entitlement.model_dump(mode='json'),
                },
            )
        )
        async with self._session_factory() as session:
            await session.execute(statement)
            await session.commit()

    async def for_buyer(self, buyer_id: str) -> tuple[Entitlement, ...]:
        statement = (
            select(Schema.entitlements.c.entitlement)
            .where(Schema.entitlements.c.buyer_id == buyer_id)
            .order_by(
                Schema.entitlements.c.granted_at.desc(),
                Schema.entitlements.c.candidate_id,
                Schema.entitlements.c.order_id,
            )
        )
        async with self._session_factory() as session:
            rows = (await session.execute(statement)).mappings().all()
        return tuple(Entitlement.model_validate(row['entitlement']) for row in rows)

    async def for_buyer_candidate(
        self, buyer_id: str, candidate_id: str
    ) -> tuple[Entitlement, ...]:
        # No state filter, on purpose: a revoked row has to stay reachable so a
        # refused download can carry its reason instead of reporting no purchase.
        statement = (
            select(Schema.entitlements.c.entitlement)
            .where(
                Schema.entitlements.c.buyer_id == buyer_id,
                Schema.entitlements.c.candidate_id == candidate_id,
            )
            .order_by(
                Schema.entitlements.c.granted_at.desc(),
                Schema.entitlements.c.candidate_id,
                Schema.entitlements.c.order_id,
            )
        )
        async with self._session_factory() as session:
            rows = (await session.execute(statement)).mappings().all()
        return tuple(Entitlement.model_validate(row['entitlement']) for row in rows)

    async def save_disclosure(self, disclosure: SellerDisclosure) -> None:
        statement = (
            insert(Schema.seller_disclosure)
            .values(
                id=SELLER_DISCLOSURE_KEY,
                disclosure=disclosure.model_dump(mode='json'),
            )
            .on_conflict_do_update(
                index_elements=['id'],
                set_={'disclosure': disclosure.model_dump(mode='json')},
            )
        )
        async with self._session_factory() as session:
            await session.execute(statement)
            await session.commit()

    async def current(self) -> SellerDisclosure | None:
        statement = select(Schema.seller_disclosure.c.disclosure).where(
            Schema.seller_disclosure.c.id == SELLER_DISCLOSURE_KEY
        )
        async with self._session_factory() as session:
            row = (await session.execute(statement)).mappings().one_or_none()
        if row is None:
            return None
        return SellerDisclosure.model_validate(row['disclosure'])

    async def save_order(self, order: Order) -> None:
        statement = (
            insert(Schema.orders)
            .values(
                order_id=order.order_id,
                buyer_id=order.buyer_id,
                state=order.state.value,
                provider_id=order.provider_id,
                provider_reference=order.provider_reference,
                created_at=order.created_at,
                order=order.model_dump(mode='json'),
            )
            .on_conflict_do_update(
                index_elements=['order_id'],
                set_={
                    'buyer_id': order.buyer_id,
                    'state': order.state.value,
                    'provider_id': order.provider_id,
                    'provider_reference': order.provider_reference,
                    'created_at': order.created_at,
                    'order': order.model_dump(mode='json'),
                },
            )
        )
        async with self._session_factory() as session:
            await session.execute(statement)
            await session.commit()

    async def by_order_id(self, order_id: str) -> Order | None:
        statement = select(Schema.orders.c.order).where(
            Schema.orders.c.order_id == order_id
        )
        async with self._session_factory() as session:
            row = (await session.execute(statement)).mappings().one_or_none()
        if row is None:
            return None
        return Order.model_validate(row['order'])

    async def by_provider_reference(
        self, provider_id: str, provider_reference: str
    ) -> Order | None:
        statement = select(Schema.orders.c.order).where(
            Schema.orders.c.provider_id == provider_id,
            Schema.orders.c.provider_reference == provider_reference,
        )
        async with self._session_factory() as session:
            row = (await session.execute(statement)).mappings().one_or_none()
        if row is None:
            return None
        return Order.model_validate(row['order'])

    async def orders_for_buyer(self, buyer_id: str) -> tuple[Order, ...]:
        statement = (
            select(Schema.orders.c.order)
            .where(Schema.orders.c.buyer_id == buyer_id)
            .order_by(
                Schema.orders.c.created_at.desc(),
                Schema.orders.c.order_id.asc(),
            )
        )
        async with self._session_factory() as session:
            rows = (await session.execute(statement)).mappings().all()
        return tuple(Order.model_validate(row['order']) for row in rows)

    async def create_account(self, account: Account) -> bool:
        """Write the account only when its email is free.

        ``ON CONFLICT DO NOTHING`` makes a duplicate registration a row count
        rather than a unique-violation exception, so the refusal stays a value.
        """
        row = self._account_row(account)
        statement = (
            insert(Schema.users)
            .values(**row)
            .on_conflict_do_nothing(index_elements=['email'])
            .returning(Schema.users.c.account_id)
        )
        async with self._session_factory() as session:
            result = await session.execute(statement)
            written = len(result.scalars().all())
            await session.commit()
        return written > 0

    async def save_account(self, account: Account) -> None:
        row = self._account_row(account)
        statement = (
            insert(Schema.users)
            .values(**row)
            .on_conflict_do_update(
                index_elements=['account_id'],
                set_=self._without_key(row, 'account_id'),
            )
        )
        async with self._session_factory() as session:
            await session.execute(statement)
            await session.commit()

    async def by_email(self, email: str) -> Account | None:
        statement = select(Schema.users.c.account).where(Schema.users.c.email == email)
        async with self._session_factory() as session:
            row = (await session.execute(statement)).mappings().one_or_none()
        if row is None:
            return None
        return Account.model_validate(row['account'])

    async def by_account_id(self, account_id: str) -> Account | None:
        statement = select(Schema.users.c.account).where(
            Schema.users.c.account_id == account_id
        )
        async with self._session_factory() as session:
            row = (await session.execute(statement)).mappings().one_or_none()
        if row is None:
            return None
        return Account.model_validate(row['account'])

    async def record_failed_sign_in(
        self, account_id: str, now: datetime, window_seconds: int
    ) -> None:
        account = await self._account_or_raise(account_id)
        attempts = account.failed_attempts + 1
        within_window = (
            account.last_failed_at is not None
            and (now - account.last_failed_at).total_seconds() <= window_seconds
        )
        if not within_window:
            attempts = 1
        await self.save_account(
            account.model_copy(
                update={'failed_attempts': attempts, 'last_failed_at': now}
            )
        )

    async def clear_failed_sign_ins(self, account_id: str) -> None:
        account = await self._account_or_raise(account_id)
        await self.save_account(
            account.model_copy(update={'failed_attempts': 0, 'last_failed_at': None})
        )

    async def save_session(self, session: Session) -> None:
        row = self._session_row(session)
        statement = (
            insert(Schema.sessions)
            .values(**row)
            .on_conflict_do_update(
                index_elements=['token_hash'],
                set_=self._without_key(row, 'token_hash'),
            )
        )
        async with self._session_factory() as db:
            await db.execute(statement)
            await db.commit()

    async def by_token_hash(self, token_hash: str) -> Session | None:
        statement = select(Schema.sessions.c.session).where(
            Schema.sessions.c.token_hash == token_hash
        )
        async with self._session_factory() as db:
            row = (await db.execute(statement)).mappings().one_or_none()
        if row is None:
            return None
        return Session.model_validate(row['session'])

    async def revoke_session(self, token_hash: str, now: datetime) -> None:
        stored = await self.by_token_hash(token_hash)
        if stored is None:
            return
        await self.save_session(stored.model_copy(update={'revoked_at': now}))

    async def revoke_other_sessions(
        self, user_id: str, token_hash: str, now: datetime
    ) -> None:
        statement = select(Schema.sessions.c.session).where(
            Schema.sessions.c.user_id == user_id
        )
        async with self._session_factory() as db:
            rows = (await db.execute(statement)).mappings().all()
        for row in rows:
            stored = Session.model_validate(row['session'])
            if stored.token_hash != token_hash:
                await self.save_session(
                    stored.model_copy(update={'revoked_at': now})
                )

    async def _account_or_raise(self, account_id: str) -> Account:
        account = await self.by_account_id(account_id)
        if account is None:
            raise ValueError(f'no account {account_id} to update')
        return account

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
    def _category_select() -> Select:
        """The category columns with their names, from one left join.

        The scalar column is labelled ``category_name`` because both tables have
        a column called ``name``; an unlabelled join would collapse the two in
        the result mapping and one of them would silently win.
        """
        return select(
            Schema.categories.c.category_id,
            Schema.categories.c.name.label('category_name'),
            Schema.categories.c.slug,
            Schema.categories.c.saleor_category_id,
            Schema.categories.c.created_at,
            Schema.category_names.c.locale,
            Schema.category_names.c.name.label('locale_name'),
        ).outerjoin(
            Schema.category_names,
            Schema.category_names.c.category_id == Schema.categories.c.category_id,
        )

    @classmethod
    def _categories_from(cls, rows: Sequence[Mapping[str, object]]) -> tuple[Category, ...]:
        """Group the joined rows into categories, in the order the query returned.

        A category with no names comes back as one row with a null locale, so a
        group is built by consecutive ``category_id`` rather than by name count.
        """
        categories: list[Category] = []
        group: list[Mapping[str, object]] = []
        for row in rows:
            if len(group) > 0 and row['category_id'] != group[0]['category_id']:
                categories.append(cls._category_from(group))
                group = []
            group.append(row)
        if len(group) > 0:
            categories.append(cls._category_from(group))
        return tuple(categories)

    @staticmethod
    def _category_from(rows: Sequence[Mapping[str, object]]) -> Category:
        first = rows[0]
        names = tuple(
            CategoryName(locale=Locale(row['locale']), name=row['locale_name'])
            for row in rows
            if row['locale'] is not None
        )
        return Category(
            category_id=first['category_id'],
            name=first['category_name'],
            slug=first['slug'],
            saleor_category_id=first['saleor_category_id'],
            created_at=first['created_at'],
            names=names,
        )

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

    @staticmethod
    def _account_row(account: Account) -> dict[str, object]:
        """Every column of ``users`` from the model, so none can fall behind."""
        return {
            'account_id': account.account_id,
            'email': account.email,
            'account': account.model_dump(mode='json'),
            'failed_attempts': account.failed_attempts,
            'last_failed_at': account.last_failed_at,
        }

    @staticmethod
    def _session_row(session: Session) -> dict[str, object]:
        """Every column of ``sessions`` from the model, so none can fall behind."""
        return {
            'token_hash': session.token_hash,
            'user_id': session.user_id,
            'created_at': session.created_at,
            'expires_at': session.expires_at,
            'revoked_at': session.revoked_at,
            'session': session.model_dump(mode='json'),
        }

    @staticmethod
    def _without_key(row: dict[str, object], key: str) -> dict[str, object]:
        """The upsert SET clause: every written column but the conflict target."""
        return {name: value for name, value in row.items() if name != key}

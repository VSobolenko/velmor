from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from packages.services.src.domain.account import Account, Session
from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.catalogue import CatalogueEntry, SaleableEntry
from packages.services.src.domain.catalogue_query import (
    CatalogueFilter,
    CatalogueMatches,
    CategoryGoodsCount,
)
from packages.services.src.domain.category import Category
from packages.services.src.domain.entitlement import Entitlement
from packages.services.src.domain.gate import GateDecision
from packages.services.src.domain.order import Order
from packages.services.src.domain.presentation import CataloguePresentation, Locale
from packages.services.src.domain.preview import CatalogueCover
from packages.services.src.domain.rights import RightsRecord
from packages.services.src.domain.seller import SellerDisclosure
from packages.services.src.persistence.contract import SELLER_DISCLOSURE_KEY


class InMemoryStore:
    """Candidate, verdict, catalogue, category and commerce storage held in process memory.

    It implements every repository protocol, as ``PostgresStore`` does, because
    the two are one contract in practice: ``pending_audit`` is an anti-join
    against the verdicts. A double that kept candidates and verdicts in separate
    objects would hand the auditor every candidate it had already decided, and a
    test written against it would prove behaviour the production store does not
    have. The commerce repositories are held here for the same reason: a test
    that exercised them against a different double would not describe the store
    the process runs.

    Insertion order is preserved so ``pending_audit`` is deterministic, which is
    what lets a test assert the order the auditor will process a batch in.
    """

    def __init__(self) -> None:
        self._candidates: dict[str, Candidate] = {}
        self._decisions: dict[str, GateDecision] = {}
        self._entries: dict[str, CatalogueEntry] = {}
        self._categories: dict[str, Category] = {}
        self._presentations: dict[tuple[str, Locale], CataloguePresentation] = {}
        self._covers: dict[str, CatalogueCover] = {}
        self._entitlements: dict[tuple[str, str], Entitlement] = {}
        self._disclosures: dict[str, SellerDisclosure] = {}
        self._orders: dict[str, Order] = {}
        self._orders_by_provider_ref: dict[tuple[str, str], str] = {}
        self._accounts: dict[str, Account] = {}
        self._accounts_by_email: dict[str, str] = {}
        self._sessions: dict[str, Session] = {}

    async def create_account(self, account: Account) -> bool:
        if account.email in self._accounts_by_email:
            return False
        self._accounts[account.account_id] = account
        self._accounts_by_email[account.email] = account.account_id
        return True

    async def save_account(self, account: Account) -> None:
        self._accounts[account.account_id] = account
        self._accounts_by_email[account.email] = account.account_id

    async def by_email(self, email: str) -> Account | None:
        account_id = self._accounts_by_email.get(email)
        return None if account_id is None else self._accounts[account_id]

    async def by_account_id(self, account_id: str) -> Account | None:
        return self._accounts.get(account_id)

    async def record_failed_sign_in(
        self, account_id: str, now: datetime, window_seconds: int
    ) -> None:
        account = self._accounts[account_id]
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
        account = self._accounts[account_id]
        await self.save_account(
            account.model_copy(update={'failed_attempts': 0, 'last_failed_at': None})
        )

    async def save_session(self, session: Session) -> None:
        self._sessions[session.token_hash] = session

    async def by_token_hash(self, token_hash: str) -> Session | None:
        return self._sessions.get(token_hash)

    async def revoke_session(self, token_hash: str, now: datetime) -> None:
        session = self._sessions.get(token_hash)
        if session is not None:
            self._sessions[token_hash] = session.model_copy(update={'revoked_at': now})

    async def revoke_other_sessions(
        self, user_id: str, token_hash: str, now: datetime
    ) -> None:
        for key, session in self._sessions.items():
            if session.user_id == user_id and key != token_hash:
                self._sessions[key] = session.model_copy(update={'revoked_at': now})

    async def upsert_many(self, candidates: tuple[Candidate, ...]) -> int:
        written = 0
        for candidate in candidates:
            if candidate.id in self._candidates:
                continue
            self._candidates[candidate.id] = candidate
            written += 1
        return written

    async def pending_audit(self, limit: int) -> tuple[Candidate, ...]:
        pending = [
            candidate
            for candidate_id, candidate in self._candidates.items()
            if candidate_id not in self._decisions
        ]
        return tuple(pending[:limit])

    async def by_candidate_id(self, candidate_id: str) -> Candidate | None:
        return self._candidates.get(candidate_id)

    async def save(self, decision: GateDecision) -> None:
        self._decisions[decision.candidate_id] = decision

    async def published(self, limit: int) -> tuple[tuple[Candidate, RightsRecord], ...]:
        return tuple(
            (self._candidates[candidate_id], decision.record)
            for candidate_id, decision in self._decisions.items()
            if decision.publishable and candidate_id in self._candidates
        )[:limit]

    async def published_count(self) -> int:
        return sum(
            1
            for candidate_id, decision in self._decisions.items()
            if decision.publishable and candidate_id in self._candidates
        )

    async def search(self, query: CatalogueFilter) -> CatalogueMatches:
        matches = self._in_catalogue_order(
            entry
            for entry in self._entries.values()
            if SaleableEntry.matches(entry)
            and (query.category_id is None or entry.category_id == query.category_id)
            and (query.license_id is None or entry.license_id == query.license_id)
        )
        return CatalogueMatches(entries=matches, total=len(matches))

    async def counts_by_category(self) -> tuple[CategoryGoodsCount, ...]:
        counts: dict[str, int] = {}
        for entry in self._entries.values():
            if not SaleableEntry.matches(entry) or entry.category_id is None:
                continue
            if entry.category_id not in counts:
                counts[entry.category_id] = 0
            counts[entry.category_id] = counts[entry.category_id] + 1
        return tuple(
            CategoryGoodsCount(category_id=category_id, count=counts[category_id])
            for category_id in sorted(counts)
        )

    async def save_entry(self, entry: CatalogueEntry) -> None:
        self._entries[entry.candidate_id] = entry

    async def by_candidate(self, candidate_id: str) -> CatalogueEntry | None:
        return self._entries.get(candidate_id)

    async def by_category(self, category_id: str) -> tuple[CatalogueEntry, ...]:
        return self._in_catalogue_order(
            entry for entry in self._entries.values() if entry.category_id == category_id
        )

    async def entries(self, limit: int) -> tuple[CatalogueEntry, ...]:
        return self._in_catalogue_order(self._entries.values())[:limit]

    async def save_category(self, category: Category) -> None:
        self._categories[category.category_id] = category

    async def by_id(self, category_id: str) -> Category | None:
        return self._categories.get(category_id)

    async def by_slug(self, slug: str) -> Category | None:
        for category in self._categories.values():
            if category.slug == slug:
                return category
        return None

    async def all(self) -> tuple[Category, ...]:
        return tuple(
            sorted(
                self._categories.values(),
                key=lambda category: (category.name, category.category_id),
            )
        )

    async def delete_category(self, category_id: str) -> None:
        self._categories.pop(category_id, None)

    async def save_presentation(self, presentation: CataloguePresentation) -> None:
        self._presentations[(presentation.candidate_id, presentation.locale)] = presentation

    async def presentations_for(
        self, candidate_id: str
    ) -> tuple[CataloguePresentation, ...]:
        return tuple(
            sorted(
                (
                    presentation
                    for (stored_id, _locale), presentation in self._presentations.items()
                    if stored_id == candidate_id
                ),
                key=lambda presentation: presentation.locale.value,
            )
        )

    async def all_presentations(self) -> tuple[CataloguePresentation, ...]:
        return tuple(
            sorted(
                self._presentations.values(),
                key=lambda presentation: (
                    presentation.candidate_id,
                    presentation.locale.value,
                ),
            )
        )

    async def save_cover(self, cover: CatalogueCover) -> None:
        self._covers[cover.candidate_id] = cover

    async def cover_for(self, candidate_id: str) -> CatalogueCover | None:
        return self._covers.get(candidate_id)

    async def all_covers(self) -> tuple[CatalogueCover, ...]:
        return tuple(
            self._covers[candidate_id] for candidate_id in sorted(self._covers)
        )

    async def save_entitlement(self, entitlement: Entitlement) -> None:
        self._entitlements[(entitlement.order_id, entitlement.candidate_id)] = entitlement

    async def for_buyer(self, buyer_id: str) -> tuple[Entitlement, ...]:
        return self._in_grant_order(
            entitlement
            for entitlement in self._entitlements.values()
            if entitlement.buyer_id == buyer_id
        )

    async def for_buyer_candidate(
        self, buyer_id: str, candidate_id: str
    ) -> tuple[Entitlement, ...]:
        return self._in_grant_order(
            entitlement
            for entitlement in self._entitlements.values()
            if entitlement.buyer_id == buyer_id
            and entitlement.candidate_id == candidate_id
        )

    async def save_disclosure(self, disclosure: SellerDisclosure) -> None:
        self._disclosures[SELLER_DISCLOSURE_KEY] = disclosure

    async def current(self) -> SellerDisclosure | None:
        return self._disclosures.get(SELLER_DISCLOSURE_KEY)

    async def save_order(self, order: Order) -> None:
        previous = self._orders.get(order.order_id)
        if previous is not None:
            self._drop_provider_index(previous)
        if order.provider_id is not None and order.provider_reference is not None:
            key = (order.provider_id, order.provider_reference)
            existing_id = self._orders_by_provider_ref.get(key)
            if existing_id is not None and existing_id != order.order_id:
                raise ValueError(
                    f'provider reference already used by order {existing_id}'
                )
            self._orders_by_provider_ref[key] = order.order_id
        self._orders[order.order_id] = order

    async def by_order_id(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)

    async def by_provider_reference(
        self, provider_id: str, provider_reference: str
    ) -> Order | None:
        order_id = self._orders_by_provider_ref.get((provider_id, provider_reference))
        if order_id is None:
            return None
        return self._orders.get(order_id)

    async def orders_for_buyer(self, buyer_id: str) -> tuple[Order, ...]:
        return self._in_order_created_order(
            order for order in self._orders.values() if order.buyer_id == buyer_id
        )

    def order_ids(self) -> tuple[str, ...]:
        return tuple(self._orders)

    def _drop_provider_index(self, order: Order) -> None:
        if order.provider_id is None or order.provider_reference is None:
            return
        key = (order.provider_id, order.provider_reference)
        if self._orders_by_provider_ref.get(key) == order.order_id:
            del self._orders_by_provider_ref[key]

    @staticmethod
    def _in_order_created_order(orders: Iterable[Order]) -> tuple[Order, ...]:
        """Most recently created first, ``order_id`` breaking a tie."""
        by_id = sorted(orders, key=lambda order: order.order_id)
        return tuple(sorted(by_id, key=lambda order: order.created_at, reverse=True))

    @staticmethod
    def _in_catalogue_order(entries: Iterable[CatalogueEntry]) -> tuple[CatalogueEntry, ...]:
        """Most recently published first, ``candidate_id`` breaking a tie.

        Two stable sorts rather than one: no single key orders descending by
        ``published_at`` and ascending by ``candidate_id`` at the same time.
        """
        by_candidate = sorted(entries, key=lambda entry: entry.candidate_id)
        return tuple(sorted(by_candidate, key=lambda entry: entry.published_at, reverse=True))

    @staticmethod
    def _in_grant_order(entitlements: Iterable[Entitlement]) -> tuple[Entitlement, ...]:
        """Most recently granted first, ``candidate_id`` then ``order_id`` breaking a tie."""
        by_order = sorted(entitlements, key=lambda entitlement: entitlement.order_id)
        by_candidate = sorted(by_order, key=lambda entitlement: entitlement.candidate_id)
        return tuple(
            sorted(by_candidate, key=lambda entitlement: entitlement.granted_at, reverse=True)
        )

    def stored_ids(self) -> tuple[str, ...]:
        return tuple(self._candidates)

    def decisions(self) -> tuple[GateDecision, ...]:
        return tuple(self._decisions.values())

    def publishable_ids(self) -> tuple[str, ...]:
        return tuple(
            candidate_id
            for candidate_id, decision in self._decisions.items()
            if decision.publishable
        )

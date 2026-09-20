from __future__ import annotations

from collections.abc import Iterable

from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.catalogue import CatalogueEntry
from packages.services.src.domain.category import Category
from packages.services.src.domain.entitlement import Entitlement
from packages.services.src.domain.gate import GateDecision
from packages.services.src.domain.order import Order
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
        self._entitlements: dict[tuple[str, str], Entitlement] = {}
        self._disclosures: dict[str, SellerDisclosure] = {}
        self._orders: dict[str, Order] = {}
        self._orders_by_provider_ref: dict[tuple[str, str], str] = {}

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

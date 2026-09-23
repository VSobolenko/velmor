from __future__ import annotations

from typing import Protocol, runtime_checkable

from packages.services.src.domain.candidate import Candidate
from packages.services.src.domain.catalogue import CatalogueEntry
from packages.services.src.domain.catalogue_query import (
    CatalogueFilter,
    CatalogueMatches,
    CategoryGoodsCount,
)
from packages.services.src.domain.category import Category
from packages.services.src.domain.entitlement import Entitlement
from packages.services.src.domain.gate import GateDecision
from packages.services.src.domain.order import Order
from packages.services.src.domain.presentation import CataloguePresentation
from packages.services.src.domain.preview import CatalogueCover
from packages.services.src.domain.rights import RightsRecord
from packages.services.src.domain.seller import SellerDisclosure

# The platform has one seller, so the disclosure is one row under this fixed key
# rather than a table that happens to hold one. Both stores import it, so the
# key exists in one place.
SELLER_DISCLOSURE_KEY: str = 'seller'


class CandidateRepository(Protocol):
    """Storage for discovered candidates.

    Deliberately narrow: this interface writes candidates and reads back the ones
    with no verdict yet. It has no opinion about rights, so it can never become
    the place a publishability decision gets made by accident.
    """

    async def upsert_many(self, candidates: tuple[Candidate, ...]) -> int:
        """Store candidates, collapsing ones already known. Returns the count written."""
        ...

    async def pending_audit(self, limit: int) -> tuple[Candidate, ...]:
        """Candidates that have no rights record yet, oldest first."""
        ...

    async def by_candidate_id(self, candidate_id: str) -> Candidate | None:
        """The candidate with this id, or ``None`` if it was never stored.

        Named ``by_candidate_id`` rather than ``by_id`` so it does not collide
        with ``CategoryRepository.by_id`` on the shared store.
        """
        ...


class RightsRecordRepository(Protocol):
    """Storage for verdicts, kept apart from candidate storage on purpose.

    Only the verification stage writes here, so the audit trail has exactly one
    author and a verdict can always be traced back to the run that produced it.
    """

    async def save(self, decision: GateDecision) -> None:
        """Persist a verdict, replacing any earlier one for the same candidate."""
        ...


class StorefrontCatalog(Protocol):
    """Read model for the storefront: the goods the gate published.

    Separate from the write repositories because it answers a different question.
    Nothing here decides anything: a good is reachable only through
    ``publishable``, so there is no query the storefront could issue that would
    list something the gate refused. Selling the good is not this interface's
    concern either - it carries the record so the page can state the licence and
    the obligations that came with the verdict.
    """

    async def published(self, limit: int) -> tuple[tuple[Candidate, RightsRecord], ...]:
        """Publishable goods, most recently decided first."""
        ...

    async def published_count(self) -> int:
        """How many publishable goods exist in total.

        Separate from the length of ``published``: that list is capped, and a page
        that reported the cap as the size of the catalogue would be stating
        something false about the business.
        """
        ...

    async def search(self, query: CatalogueFilter) -> CatalogueMatches:
        """Catalogued goods matching the filters a store can apply on its own.

        Category and licence are columns, so they are applied here. The text
        term and the ordering are not: both depend on the title resolved for a
        locale, which the service owns. ``total`` counts every match, never the
        page a caller asked for.
        """
        ...

    async def counts_by_category(self) -> tuple[CategoryGoodsCount, ...]:
        """How many saleable goods each category holds.

        A category holding no saleable good is absent from the result; a caller
        reporting the shop's categories reports zero for it.
        """
        ...


@runtime_checkable
class CatalogueEntryRepository(Protocol):
    """Storage for catalogue entries: the goods the shop offers for sale.

    An entry is a projection of a decision onto a shop, not a rights record, so
    ``save_entry`` replaces the row for a good instead of appending one: a good
    is published and can later be withdrawn, and the storefront has to read the
    current state of the catalogue. The append-only audit trail is
    ``rights_records``, which this interface never touches. It must never become
    the place a publishability decision is made either: an entry arrives already
    justified by a ``GateDecision``, and nothing here re-derives that.
    """

    async def save_entry(self, entry: CatalogueEntry) -> None:
        """Store the entry for its good, replacing any earlier one."""
        ...

    async def by_candidate(self, candidate_id: str) -> CatalogueEntry | None:
        """The entry for one good, or ``None`` if it is not in the catalogue."""
        ...

    async def by_category(self, category_id: str) -> tuple[CatalogueEntry, ...]:
        """The entries in one category, most recently published first.

        An empty tuple means the category holds no entries, which is the one
        question a caller deciding whether the category can be removed asks.
        """
        ...

    async def entries(self, limit: int) -> tuple[CatalogueEntry, ...]:
        """The catalogue, most recently published first, capped at ``limit``."""
        ...


@runtime_checkable
class CategoryRepository(Protocol):
    """Storage for storefront categories the operator (or agent) manages.

    Categories are explicit rows, not something inferred at render time from a
    model call (design D4). ``save_category`` upserts by ``category_id``;
    ``delete_category`` of a missing id is a no-op. ``all`` returns every
    category ordered by the scalar ``name`` ascending, then ``category_id``
    ascending; that order does not depend on the language a buyer reads.

    A category carries its buyer-facing names per locale in ``names``. The
    scalar ``name`` is the external-catalogue and ordering value, not a
    buyer-facing one: a surface resolves the name it shows from ``names`` for
    the language being read, and a category with no names decodes as ``()``
    rather than failing the read.
    """

    async def save_category(self, category: Category) -> None:
        """Store the category, replacing any earlier one with the same id."""
        ...

    async def by_id(self, category_id: str) -> Category | None:
        """The category with this id, or ``None`` if it does not exist."""
        ...

    async def by_slug(self, slug: str) -> Category | None:
        """The category with this slug, or ``None`` if it does not exist."""
        ...

    async def all(self) -> tuple[Category, ...]:
        """Every category, ordered by name ascending then category_id ascending."""
        ...

    async def delete_category(self, category_id: str) -> None:
        """Remove the category. A missing id is a no-op."""
        ...


@runtime_checkable
class CataloguePresentationRepository(Protocol):
    """Storage for the buyer-facing copy of a catalogued good, one row per locale.

    Keyed by ``(candidate_id, locale)`` rather than by candidate with three
    nullable columns, because resolving a locale is then a lookup and a
    fallback instead of a truthiness test over a mostly-empty record. A
    presentation carries no price and no licence, so this interface can never
    become a second opinion about what may be sold.
    """

    async def save_presentation(self, presentation: CataloguePresentation) -> None:
        """Store the row for its ``(candidate_id, locale)``, replacing any earlier one."""
        ...

    async def presentations_for(
        self, candidate_id: str
    ) -> tuple[CataloguePresentation, ...]:
        """Every locale stored for one good, ordered by locale."""
        ...

    async def all_presentations(self) -> tuple[CataloguePresentation, ...]:
        """Every stored presentation, ordered by candidate id then locale.

        Named ``all_presentations`` rather than ``all`` because
        ``CategoryRepository.all`` already holds that name on the shared store.
        """
        ...


@runtime_checkable
class CatalogueCoverRepository(Protocol):
    """Storage for an operator-attached cover, one row per good.

    ``digest`` locates bytes in the asset cache and never names the origin: a
    cover is presentation, it never substitutes for the good at delivery, and
    reading it must not be a way to obtain the good.
    """

    async def save_cover(self, cover: CatalogueCover) -> None:
        """Store the cover for its good, replacing any earlier one."""
        ...

    async def cover_for(self, candidate_id: str) -> CatalogueCover | None:
        """The cover attached to this good, or ``None`` if none was attached.

        Named ``cover_for`` rather than ``by_candidate`` because
        ``CatalogueEntryRepository.by_candidate`` already holds that name on the
        shared store.
        """
        ...

    async def all_covers(self) -> tuple[CatalogueCover, ...]:
        """Every attached cover, ordered by candidate id."""
        ...


@runtime_checkable
class EntitlementRepository(Protocol):
    """Storage for a buyer's right to download one good.

    An entitlement is a fact about one purchase, keyed by the order that paid
    for it, so a refund revokes exactly what it refunded and a second order for
    the same good survives. It must never become a query that filters by state:
    ``for_buyer_candidate`` returns every row for that buyer and good, because a
    refused download has to tell "never bought" apart from "revoked, and here is
    why", and the reason is only reachable if the revoked row is returned.
    """

    async def save_entitlement(self, entitlement: Entitlement) -> None:
        """Store the entitlement, replacing any earlier one for its order and good."""
        ...

    async def for_buyer(self, buyer_id: str) -> tuple[Entitlement, ...]:
        """One buyer's entitlements, most recently granted first."""
        ...

    async def for_buyer_candidate(
        self, buyer_id: str, candidate_id: str
    ) -> tuple[Entitlement, ...]:
        """Every entitlement that buyer holds for one good, of every state.

        An empty tuple means the buyer never bought the good. A revoked
        entitlement is returned with its reason; what to do about it is the
        caller's decision, not this interface's.
        """
        ...


@runtime_checkable
class SellerDisclosureRepository(Protocol):
    """Storage for the seller's legal identity, written by an operator command.

    The platform has one seller, so there is one row under
    ``SELLER_DISCLOSURE_KEY`` and ``save_disclosure`` replaces it. The disclosure
    is stored data and not a setting (design D7), so this interface must never
    gain a default or a "best effort" accessor that makes an unconfigured item
    quiet: an absent item is what makes checkout refuse.
    """

    async def save_disclosure(self, disclosure: SellerDisclosure) -> None:
        """Store the disclosure, replacing the one configured before it."""
        ...

    async def current(self) -> SellerDisclosure | None:
        """The configured disclosure, or ``None`` if none was configured.

        ``None`` is the row that does not exist yet, which the completeness
        check reports as every item missing. It is not an empty disclosure.
        """
        ...


@runtime_checkable
class OrderRepository(Protocol):
    """Storage for checkout orders.

    ``save_order`` upserts by ``order_id``. Provider correlation uses
    ``by_provider_reference`` when a notification arrives. Uniqueness of
    ``(provider_id, provider_reference)`` when the reference is set is a store
    invariant: Postgres uses a partial unique index; InMemory enforces it on
    write. Write and read methods are named after the subject
    (``save_order``, ``by_order_id``) rather than ``save`` / ``by_id``, because
    ``RightsRecordRepository.save`` and ``CategoryRepository.by_id`` already
    hold those names on both stores.
    """

    async def save_order(self, order: Order) -> None:
        """Store the order, replacing any earlier one with the same id."""
        ...

    async def by_order_id(self, order_id: str) -> Order | None:
        """The order with this id, or ``None`` if it does not exist."""
        ...

    async def by_provider_reference(
        self, provider_id: str, provider_reference: str
    ) -> Order | None:
        """The order correlated with this provider payment id, or ``None``."""
        ...

    async def orders_for_buyer(self, buyer_id: str) -> tuple[Order, ...]:
        """Orders for this buyer, most recent ``created_at`` first, then ``order_id``.

        Task 5.5 asked for ``for_buyer``; that name is already taken by
        ``EntitlementRepository.for_buyer`` on the shared store, so this method
        follows the same disambiguation as ``save_order`` / ``by_order_id``.
        """
        ...

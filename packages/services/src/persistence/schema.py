from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Index, MetaData, Table, Text, func
from sqlalchemy.dialects.postgresql import JSONB


class Schema:
    """Table definitions for the Velmor store.

    Declared once, here, so the shape of persisted data is reviewable in one
    place. Scalar columns carry what the pipeline filters and joins on. The full
    rights record is kept as JSONB beside them because it is a nested audit
    document: its evidence array must survive verbatim, and flattening it into
    columns nobody queries would destroy the thing it exists to preserve.
    """

    metadata = MetaData()

    candidates = Table(
        'candidates',
        metadata,
        Column('id', Text, primary_key=True),
        Column('source_id', Text, nullable=False, index=True),
        Column('title', Text, nullable=False),
        Column('landing_url', Text, nullable=False),
        Column('creator', Text, nullable=True),
        Column('content_type', Text, nullable=False),
        Column('declared_license_id', Text, nullable=True),
        Column('declared_license_text', Text, nullable=True),
        Column('download_url', Text, nullable=True),
        Column('size_bytes', BigInteger, nullable=True),
        Column(
            'discovered_at',
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )

    rights_records = Table(
        'rights_records',
        metadata,
        Column('candidate_id', Text, primary_key=True),
        Column('source_id', Text, nullable=False, index=True),
        Column('license_id', Text, nullable=True),
        Column('verdict', Text, nullable=False),
        Column('publishable', Boolean, nullable=False),
        Column('reason', Text, nullable=False),
        Column('record', JSONB, nullable=False),
        Column('decided_at', DateTime(timezone=True), nullable=False),
    )

    catalogue_entries = Table(
        'catalogue_entries',
        metadata,
        Column('candidate_id', Text, primary_key=True),
        Column('source_id', Text, nullable=False),
        Column('category_id', Text, nullable=True, index=True),
        Column('listing', Text, nullable=False),
        Column('state', Text, nullable=False),
        Column('published_at', DateTime(timezone=True), nullable=False),
        Column('entry', JSONB, nullable=False),
    )

    categories = Table(
        'categories',
        metadata,
        Column('category_id', Text, primary_key=True),
        Column('name', Text, nullable=False),
        Column('slug', Text, nullable=False, unique=True, index=True),
        Column('saleor_category_id', Text, nullable=False),
        Column('created_at', DateTime(timezone=True), nullable=False),
        Column('category', JSONB, nullable=False),
    )

    # Buyer-facing names live in their own table keyed (category_id, locale),
    # mirroring catalogue_presentations. The shape adds a table rather than
    # altering `categories`, because ensure_schema() is create_all and never
    # alters, and the table already exists in the deployed databases.
    category_names = Table(
        'category_names',
        metadata,
        Column('category_id', Text, primary_key=True),
        Column('locale', Text, primary_key=True),
        Column('name', Text, nullable=False),
    )

    catalogue_presentations = Table(
        'catalogue_presentations',
        metadata,
        Column('candidate_id', Text, primary_key=True),
        Column('locale', Text, primary_key=True),
        Column('title', Text, nullable=False),
        Column('source', Text, nullable=False),
        Column('updated_at', DateTime(timezone=True), nullable=False),
        Column('presentation', JSONB, nullable=False),
    )

    catalogue_covers = Table(
        'catalogue_covers',
        metadata,
        Column('candidate_id', Text, primary_key=True),
        Column('source', Text, nullable=False),
        Column('attached_at', DateTime(timezone=True), nullable=False),
        Column('cover', JSONB, nullable=False),
    )

    entitlements = Table(
        'entitlements',
        metadata,
        Column('order_id', Text, primary_key=True),
        Column('candidate_id', Text, primary_key=True),
        Column('buyer_id', Text, nullable=False, index=True),
        Column('state', Text, nullable=False),
        Column('granted_at', DateTime(timezone=True), nullable=False),
        Column('entitlement', JSONB, nullable=False),
    )

    seller_disclosure = Table(
        'seller_disclosure',
        metadata,
        Column('id', Text, primary_key=True),
        Column('disclosure', JSONB, nullable=False),
    )

    orders = Table(
        'orders',
        metadata,
        Column('order_id', Text, primary_key=True),
        Column('buyer_id', Text, nullable=False, index=True),
        Column('state', Text, nullable=False),
        Column('provider_id', Text, nullable=True),
        Column('provider_reference', Text, nullable=True),
        Column('created_at', DateTime(timezone=True), nullable=False),
        Column('order', JSONB, nullable=False),
    )

    Index(
        'uq_orders_provider_reference',
        orders.c.provider_id,
        orders.c.provider_reference,
        unique=True,
        postgresql_where=orders.c.provider_reference.isnot(None),
    )

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Column, DateTime, MetaData, Table, Text, func
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

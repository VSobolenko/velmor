"""Upsert a complete fictional seller disclosure for local/dev checkout.

The text is clearly demo-only and must not be treated as a real company claim.
"""

from __future__ import annotations

import asyncio
from datetime import date

import typer
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from packages.api.src.configs.settings import CommerceSettings
from packages.core.src.bootstrap.observability import Observability
from packages.core.src.bootstrap.settings_loader import SettingsLoader
from packages.services.src.commerce.disclosure import SellerDisclosureCheck
from packages.services.src.domain.seller import SellerDisclosure
from packages.services.src.persistence.postgres import PostgresStore


class SeedDisclosureCommand:
    """Write a complete demo ``SellerDisclosure`` row into the store."""

    SERVICE_NAME = 'velmor-seed-disclosure'

    DEMO_DISCLOSURE = SellerDisclosure(
        legal_name='DEMO Velmor Example LLC (fictional — not a real company)',
        registration_number='DEMO-REG-000000',
        registration_date=date(2020, 1, 1),
        registration_authority='Demo Registration Authority (fictional)',
        shop_register_number='DEMO-SHOP-0001',
        postal_address='1 Demo Street, Example City, Demo Country (fictional)',
        working_hours='Mon-Fri 09:00-17:00 (demo hours)',
        contact_details='demo-support@example.invalid',
        payment_rules=(
            'Demo payment rules: digital goods sold for demonstration only; '
            'no real payment rails are required in stub mode.'
        ),
        return_rules=(
            'Demo return rules: digital demo goods are not returnable after download.'
        ),
        payment_system_marks=('stub', 'demo'),
    )

    def __init__(self, loader: SettingsLoader) -> None:
        self._settings = CommerceSettings(loader)

    def run(self) -> None:
        Observability(service_name=self.SERVICE_NAME).configure(self._settings)
        asyncio.run(self._seed())

    async def _seed(self) -> None:
        engine = create_async_engine(self._settings.database_dsn, pool_pre_ping=True)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        store = PostgresStore(engine, session_factory)
        disclosure = self.DEMO_DISCLOSURE
        missing = SellerDisclosureCheck().incomplete(disclosure)
        if missing != ():
            raise RuntimeError(
                f'demo disclosure is incomplete; missing: '
                f'{", ".join(item.value for item in missing)}'
            )
        await store.save_disclosure(disclosure)
        await engine.dispose()
        typer.echo('seeded seller disclosure (complete=true)')
        typer.echo(f'legal_name={disclosure.legal_name}')

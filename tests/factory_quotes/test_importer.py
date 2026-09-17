import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import SupplierProfile
from models import AuditLog, Base, FactoryCost, FactoryQuoteRow, ImportBatch
from modules.factory_quotes.importer import FactoryQuoteImporter
from modules.factory_quotes.schemas import (
    DuplicateFileError,
    NormalizedQuote,
    VariantType,
)


def record(cost: str) -> NormalizedQuote:
    return NormalizedQuote(
        supplier_code="LINGDIAN",
        product_type="PAINT_BY_NUMBERS",
        colors_count=24,
        width_cm=Decimal("40"),
        height_cm=Decimal("50"),
        size_code="40x50",
        variant_type=VariantType.UNFRAMED,
        unit_cost=Decimal(cost),
        currency="CNY",
        shipping_included=False,
        source_sheet="Sheet1",
        source_row_number=10,
        source_column="C",
        raw_color="24色",
        raw_size="40*50cm/16*20inch",
        raw_cost=cost,
        raw_payload={"raw_cost": cost},
    )


@pytest.mark.asyncio
async def test_idempotency_update_and_audit() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    importer = FactoryQuoteImporter()
    profile = SupplierProfile(
        name="领典", currency="CNY", country_code="US", timezone="America/Los_Angeles"
    )
    first_batch = uuid.uuid4()

    async with sessions() as session:
        first_plan = await importer.commit(
            session,
            batch_id=first_batch,
            supplier_code="LINGDIAN",
            supplier_profile=profile,
            source_filename="quote.xlsx",
            source_sha256="a" * 64,
            source_sheet="Sheet1",
            effective_date=date(2026, 9, 15),
            records=[record("44")],
            force=False,
            report_path="report.xlsx",
            started_at=datetime.now(UTC),
        )
    assert first_plan.insert_count == 1

    async with sessions() as session:
        with pytest.raises(DuplicateFileError):
            await importer.plan(session, "LINGDIAN", "a" * 64, [record("44")], force=False)

    async with sessions() as session:
        second_plan = await importer.commit(
            session,
            batch_id=uuid.uuid4(),
            supplier_code="LINGDIAN",
            supplier_profile=profile,
            source_filename="quote-updated.xlsx",
            source_sha256="b" * 64,
            source_sheet="Sheet1",
            effective_date=date(2026, 9, 15),
            records=[record("46")],
            force=False,
            report_path="report-2.xlsx",
            started_at=datetime.now(UTC),
        )
    assert second_plan.update_count == 1

    async with sessions() as session:
        cost_count = await session.scalar(select(func.count()).select_from(FactoryCost))
        batch_count = await session.scalar(select(func.count()).select_from(ImportBatch))
        row_count = await session.scalar(select(func.count()).select_from(FactoryQuoteRow))
        audit_count = await session.scalar(select(func.count()).select_from(AuditLog))
        stored_cost = await session.scalar(select(FactoryCost))

    assert cost_count == 1
    assert batch_count == 2
    assert row_count == 2
    assert audit_count == 4
    assert stored_cost is not None
    assert stored_cost.base_product_cost == Decimal("46.00")
    assert stored_cost.total_variable_cost is None
    assert stored_cost.domestic_shipping_cost is None
    await engine.dispose()

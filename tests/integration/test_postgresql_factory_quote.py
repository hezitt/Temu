import os
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import delete, inspect, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import SupplierProfile
from models import AuditLog, FactoryCost, FactoryQuoteRow, ImportBatch, Supplier
from modules.factory_quotes.importer import FactoryQuoteImporter
from modules.factory_quotes.schemas import NormalizedQuote, VariantType


@pytest.mark.postgresql
@pytest.mark.asyncio
async def test_real_postgresql_quote_insert() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("Set TEST_DATABASE_URL to run the PostgreSQL integration test")

    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        assert connection.dialect.name == "postgresql"
        table_names = await connection.run_sync(lambda sync: inspect(sync).get_table_names())
        assert "factory_quote_rows" in table_names

    code = f"TEST_{uuid.uuid4().hex[:12].upper()}"
    batch_id = uuid.uuid4()
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    record = NormalizedQuote(
        supplier_code=code,
        product_type="PAINT_BY_NUMBERS",
        colors_count=24,
        width_cm=Decimal("40"),
        height_cm=Decimal("50"),
        size_code="40x50",
        variant_type=VariantType.UNFRAMED,
        unit_cost=Decimal("44"),
        currency="CNY",
        source_sheet="Sheet1",
        source_row_number=10,
        source_column="C",
    )
    importer = FactoryQuoteImporter()
    profile = SupplierProfile(name="Integration Test", currency="CNY", country_code="US")

    try:
        async with sessions() as session:
            await importer.commit(
                session,
                batch_id=batch_id,
                supplier_code=code,
                supplier_profile=profile,
                source_filename="integration.xlsx",
                source_sha256=uuid.uuid4().hex * 2,
                source_sheet="Sheet1",
                effective_date=date.today(),
                records=[record],
                force=False,
                report_path="integration.xlsx",
                started_at=datetime.now(UTC),
            )
        async with sessions() as session:
            stored = await session.scalar(
                select(FactoryCost).join(Supplier).where(Supplier.supplier_code == code)
            )
            assert stored is not None
            assert stored.base_product_cost == Decimal("44.00")
            assert stored.total_variable_cost is None
    finally:
        async with sessions.begin() as session:
            supplier_id = await session.scalar(
                select(Supplier.id).where(Supplier.supplier_code == code)
            )
            await session.execute(delete(AuditLog).where(AuditLog.correlation_id == batch_id))
            if supplier_id is not None:
                await session.execute(
                    delete(FactoryQuoteRow).where(FactoryQuoteRow.supplier_id == supplier_id)
                )
                await session.execute(
                    delete(FactoryCost).where(FactoryCost.supplier_id == supplier_id)
                )
                await session.execute(
                    delete(ImportBatch).where(ImportBatch.supplier_id == supplier_id)
                )
                await session.execute(delete(Supplier).where(Supplier.id == supplier_id))
        await engine.dispose()

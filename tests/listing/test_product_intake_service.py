import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.config import Settings
from models import SKU, Base, FactoryCost, Product, Supplier
from models.enums import CostCompletenessStatus, ValidationStatus
from services.product_intake_service import ProductIntakeService


@pytest.mark.asyncio
async def test_product_intake_is_idempotent(tmp_path: Path) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async with sessions() as session, session.begin():
        supplier = Supplier(supplier_code="LINGDIAN", name="Lingdian")
        session.add(supplier)
        await session.flush()
        for width, height, framed, cost in (
            (30, 40, True, "30.00"),
            (40, 50, True, "40.00"),
            (30, 40, False, "10.00"),
            (40, 50, False, "15.00"),
        ):
            session.add(
                FactoryCost(
                    supplier_id=supplier.id,
                    product_type="PAINT_BY_NUMBERS",
                    colors_count=24,
                    source_size_label=f"{width}x{height}",
                    size_code=f"{width}{height}",
                    width_cm=Decimal(width),
                    height_cm=Decimal(height),
                    framed=framed,
                    base_product_cost=Decimal(cost),
                    currency="CNY",
                    effective_from=date.today(),
                    validation_status=ValidationStatus.VALID,
                    cost_completeness_status=CostCompletenessStatus.INCOMPLETE,
                )
            )

    intake = tmp_path / "intake.json"
    intake.write_text(
        json.dumps(
            {
                "status": "SUBMITTED_PENDING_REVIEW_WITH_EXTERNAL_IDS",
                "marketplace": "US",
                "store_mode": "SEMI_MANAGED",
                "category_path": "adult paint by numbers",
                "publishing_system": "DIANXIAOMI",
                "fulfillment_system": "FANGGUO",
                "identifiers": {
                    "factory_design_code": "LD000001",
                    "internal_spu_item_code": "PBN-LD000001",
                },
                "submission": {"review_status": "PENDING"},
                "proposed_content": {
                    "title_en": "Radio and Plant Paint by Numbers",
                    "theme_tags": ["Still Life"],
                    "style_tags": ["Minimalist"],
                },
                "known_variants": [
                    {"width_cm": 30, "height_cm": 40, "colors_count": 24, "framed": True},
                    {"width_cm": 40, "height_cm": 50, "colors_count": 24, "framed": True},
                    {"width_cm": 30, "height_cm": 40, "colors_count": 24, "framed": False},
                    {"width_cm": 40, "height_cm": 50, "colors_count": 24, "framed": False},
                ],
                "source_assets": [
                    {"path": "main.jpg", "role": "MAIN_IMAGE_CANDIDATE"},
                ],
                "blocking_fields": ["review_result"],
            }
        ),
        encoding="utf-8",
    )

    service = ProductIntakeService(Settings(), sessions)
    preview = await service.run(intake_path=intake, supplier_code="LINGDIAN", commit=False)
    assert preview["inserted"] == 6

    first = await service.run(intake_path=intake, supplier_code="LINGDIAN", commit=True)
    assert first["inserted"] == 6
    second = await service.run(intake_path=intake, supplier_code="LINGDIAN", commit=True)
    assert second["unchanged"] == 4
    assert second["inserted"] == 0

    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(Product)) == 1
        skus = (await session.scalars(select(SKU).order_by(SKU.factory_sku))).all()
    assert len(skus) == 4
    assert all(sku.resolved_factory_cost_id is not None for sku in skus)
    assert all(sku.shipping_cost_usd == Decimal("4.00") for sku in skus)
    await engine.dispose()

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from models import SKU, Base, Design, Product, Supplier, TemuListing
from models.enums import ListingStatus
from modules.listing.external_ids import (
    DianxiaomiListingObservation,
    ObservedSkuMapping,
    load_dianxiaomi_listing_observation,
)
from services.listing_external_id_service import (
    ListingExternalIdService,
    ListingExternalIdSyncError,
)


def _intake_payload() -> dict[str, object]:
    return {
        "marketplace": "US",
        "identifiers": {
            "internal_spu_item_code": "PBN-LD000001",
            "dianxiaomi_spu": "5569462031",
            "temu_spu": None,
        },
        "external_identifiers_observed_in_dianxiaomi": {
            "spu_id": "5569462031",
            "skc_id": "54471877244",
            "temu_seller_center_confirmation_pending": True,
            "sku_mappings": [
                {
                    "sku_item_code": "PBN-LD000001-3040-24-F",
                    "sku_id": "35894215932",
                },
                {
                    "sku_item_code": "PBN-LD000001-4050-24-U",
                    "sku_id": "64561517268",
                },
            ],
        },
        "submission": {
            "channel": "DIANXIAOMI_MANUAL",
            "review_status": "PENDING",
            "lifecycle_displayed": "--",
        },
    }


def test_load_dianxiaomi_listing_observation(tmp_path: Path) -> None:
    intake = tmp_path / "intake.json"
    intake.write_text(json.dumps(_intake_payload()), encoding="utf-8")
    observed_at = datetime(2026, 9, 20, 10, 30, tzinfo=UTC)

    observation = load_dianxiaomi_listing_observation(
        intake,
        observed_at=observed_at,
    )

    assert observation.internal_spu_item_code == "PBN-LD000001"
    assert observation.dianxiaomi_spu_id == "5569462031"
    assert observation.temu_spu_id is None
    assert observation.temu_skc_id == "54471877244"
    assert observation.observed_at == observed_at
    assert observation.source_sha256
    assert [mapping.temu_sku_id for mapping in observation.sku_mappings] == [
        "35894215932",
        "64561517268",
    ]


def test_load_rejects_non_object_sku_mapping(tmp_path: Path) -> None:
    payload = _intake_payload()
    external = payload["external_identifiers_observed_in_dianxiaomi"]
    assert isinstance(external, dict)
    external["sku_mappings"] = ["invalid"]
    intake = tmp_path / "invalid.json"
    intake.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="sku_mappings entry must be an object"):
        load_dianxiaomi_listing_observation(intake)


def _observation(sku_codes: list[str]) -> DianxiaomiListingObservation:
    external_ids = ["35894215932", "38745519632", "10832717802", "64561517268"]
    return DianxiaomiListingObservation(
        internal_spu_item_code="PBN-LD000001",
        dianxiaomi_spu_id="5569462031",
        temu_skc_id="54471877244",
        review_status="PENDING",
        lifecycle_status="--",
        observed_at=datetime(2026, 9, 20, 10, 30, tzinfo=UTC),
        source_file_name="first_product.intake.json",
        source_sha256="a" * 64,
        sku_mappings=[
            ObservedSkuMapping(sku_item_code=code, temu_sku_id=external_id)
            for code, external_id in zip(sku_codes, external_ids, strict=True)
        ],
        raw_payload=_intake_payload(),
    )


@pytest.mark.asyncio
async def test_external_listing_id_sync_is_safe_and_idempotent() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    sku_codes = [
        "PBN-LD000001-3040-24-F",
        "PBN-LD000001-4050-24-F",
        "PBN-LD000001-3040-24-U",
        "PBN-LD000001-4050-24-U",
    ]

    async with sessions() as session, session.begin():
        supplier = Supplier(supplier_code="LINGDIAN", name="领典")
        design = Design(design_code="LD000001", name="Radio and plant")
        session.add_all([supplier, design])
        await session.flush()
        product = Product(
            design_id=design.id,
            internal_product_code="PBN-LD000001",
            title="Radio and Plant Paint by Numbers",
        )
        session.add(product)
        await session.flush()
        for index, sku_code in enumerate(sku_codes):
            session.add(
                SKU(
                    product_id=product.id,
                    design_id=design.id,
                    supplier_id=supplier.id,
                    factory_sku=sku_code,
                    size_label="30x40cm" if "3040" in sku_code else "40x50cm",
                    width_cm=Decimal("30") if "3040" in sku_code else Decimal("40"),
                    height_cm=Decimal("40") if "3040" in sku_code else Decimal("50"),
                    colors_count=24,
                    framed=sku_code.endswith("-F"),
                    image_path=f"image-{index}.jpg",
                )
            )

    service = ListingExternalIdService(sessions)
    observation = _observation(sku_codes)

    preview = await service.run(
        observation=observation,
        supplier_code="LINGDIAN",
        store_code="US_MAIN",
        commit=False,
    )
    assert preview["inserted"] == 4
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(TemuListing)) == 0

    first = await service.run(
        observation=observation,
        supplier_code="LINGDIAN",
        store_code="US_MAIN",
        commit=True,
    )
    assert first["inserted"] == 4

    second = await service.run(
        observation=observation,
        supplier_code="LINGDIAN",
        store_code="US_MAIN",
        commit=True,
    )
    assert second["unchanged"] == 4
    assert second["updated"] == 0

    async with sessions() as session:
        rows = (
            await session.scalars(select(TemuListing).order_by(TemuListing.temu_sku_id))
        ).all()
    assert len(rows) == 4
    assert {row.dianxiaomi_spu_id for row in rows} == {"5569462031"}
    assert {row.temu_skc_id for row in rows} == {"54471877244"}
    assert {row.temu_sku_id for row in rows} == {
        "10832717802",
        "35894215932",
        "38745519632",
        "64561517268",
    }
    assert {row.status for row in rows} == {ListingStatus.SUBMITTED}
    assert all(row.temu_spu is None for row in rows)
    await engine.dispose()


@pytest.mark.asyncio
async def test_external_listing_id_sync_rejects_missing_internal_sku() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session, session.begin():
        session.add(Supplier(supplier_code="LINGDIAN", name="领典"))

    with pytest.raises(ListingExternalIdSyncError, match="internal SKUs are missing"):
        await ListingExternalIdService(sessions).run(
            observation=_observation(
                [
                    "PBN-LD000001-3040-24-F",
                    "PBN-LD000001-4050-24-F",
                    "PBN-LD000001-3040-24-U",
                    "PBN-LD000001-4050-24-U",
                ]
            ),
            supplier_code="LINGDIAN",
            store_code="US_MAIN",
            commit=False,
        )
    await engine.dispose()

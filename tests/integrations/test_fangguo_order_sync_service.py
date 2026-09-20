from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from integrations.fangguo.schemas import (
    FangguoOrderDetail,
    FangguoOrderItem,
    FangguoTid,
    FangguoTidListRequest,
    FangguoTidPage,
)
from models import (
    SKU,
    Base,
    Design,
    FulfillmentOrder,
    IntegrationConnection,
    IntegrationRun,
    IntegrationSyncCursor,
    Product,
    SalesOrder,
    SalesOrderItem,
    SalesOrderShipment,
    Store,
    Supplier,
    TemuListing,
)
from models.enums import IntegrationConnectionStatus, IntegrationProvider
from services.fangguo_order_sync_service import FangguoOrderSyncService


class FakeFangguoOrderReader:
    def __init__(self, detail: FangguoOrderDetail) -> None:
        self.detail = detail
        self.requests: list[FangguoTidListRequest] = []

    async def list_order_tids(self, request: FangguoTidListRequest) -> FangguoTidPage:
        self.requests.append(request)
        return FangguoTidPage(list=[FangguoTid(tid=self.detail.tid)], total=1)

    async def get_order_detail(self, tid: str) -> FangguoOrderDetail:
        assert tid == self.detail.tid
        return self.detail


@pytest.mark.asyncio
async def test_fangguo_order_sync_is_idempotent_and_matches_sku() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async with sessions() as session, session.begin():
        store = Store(store_code="US_MAIN", display_name="Temu US Main")
        supplier = Supplier(supplier_code="LINGDIAN", name="Lingdian")
        design = Design(design_code="DESIGN-LD000001", factory_design_code="LD000001")
        session.add_all([store, supplier, design])
        await session.flush()
        api_connection = IntegrationConnection(
            store_id=store.id,
            provider=IntegrationProvider.FANGGUO,
            connection_name="merchant-api",
            status=IntegrationConnectionStatus.ACTIVE,
            credential_reference="env:FANGGUO__API_KEY",
        )
        product = Product(
            design_id=design.id,
            internal_product_code="PBN-LD000001",
            title="Radio and Plant",
        )
        session.add_all([api_connection, product])
        await session.flush()
        sku = SKU(
            product_id=product.id,
            design_id=design.id,
            supplier_id=supplier.id,
            factory_sku="PBN-LD000001-3040-24-U",
            temu_sku="PBN-LD000001-3040-24-U",
            size_label="30x40cm",
            width_cm=Decimal("30"),
            height_cm=Decimal("40"),
            colors_count=24,
            framed=False,
        )
        session.add(sku)
        await session.flush()
        session.add(
            TemuListing(
                sku_id=sku.id,
                store_code="US_MAIN",
                temu_sku_id="10832717802",
            )
        )

    detail = FangguoOrderDetail(
        id="fangguo-record-1",
        order_type=0,
        factory_id=3000046,
        system_tid="SYS-1",
        tid="T-1",
        platform=225,
        fulfillment_status=4,
        external_status_description="待发货",
        platform_description="Temu(半托管-美区)",
        store_name="US Main",
        buyer_remark="must not be persisted",
        items=[
            FangguoOrderItem(
                id="item-1",
                oid="OID-1",
                title="Paint by numbers",
                num=2,
                price=Decimal("12.50"),
                outerIid="PBN-LD000001-3040-24-U",
                shopMappingSku="PBN-LD000001-3040-24-U",
                originalSkuId="10832717802",
                originalGoodsId="goods-1",
                logisticsOrderNum="TRACK-1",
                logisticsCompanyCode="UPS",
            )
        ],
    )
    reader = FakeFangguoOrderReader(detail)
    service = FangguoOrderSyncService(sessions, reader)
    start = datetime(2026, 9, 21, 0, 0, tzinfo=UTC)
    end = datetime(2026, 9, 21, 3, 0, tzinfo=UTC)

    first = await service.run(
        store_code="US_MAIN",
        start_time=start,
        end_time=end,
        commit=True,
    )
    second = await service.run(
        store_code="US_MAIN",
        start_time=start,
        end_time=end,
        commit=True,
    )

    assert first["inserted_orders"] == 1
    assert first["inserted_items"] == 1
    assert first["matched_items"] == 1
    assert second["inserted_orders"] == 0
    assert second["inserted_items"] == 0
    assert second["updated_orders"] == 0
    assert reader.requests[0].platform_type == 225

    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(SalesOrder)) == 1
        assert await session.scalar(select(func.count()).select_from(SalesOrderItem)) == 1
        assert await session.scalar(select(func.count()).select_from(FulfillmentOrder)) == 1
        assert await session.scalar(select(func.count()).select_from(SalesOrderShipment)) == 1
        assert await session.scalar(select(func.count()).select_from(IntegrationSyncCursor)) == 1
        assert await session.scalar(select(func.count()).select_from(IntegrationRun)) == 2
        order = await session.scalar(select(SalesOrder))
        item = await session.scalar(select(SalesOrderItem))

    assert order is not None
    assert order.total_amount == Decimal("25.00")
    assert "buyer_remark" not in order.raw_payload
    assert item is not None
    assert item.sku_id is not None
    assert item.temu_listing_id is not None
    await engine.dispose()

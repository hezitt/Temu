import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from integrations.fangguo.schemas import (
    FangguoOrderDetail,
    FangguoOrderItem,
    FangguoTidListRequest,
    FangguoTidPage,
)
from models import (
    SKU,
    FulfillmentOrder,
    IntegrationConnection,
    IntegrationRun,
    IntegrationSyncCursor,
    SalesOrder,
    SalesOrderItem,
    SalesOrderShipment,
    Store,
    TemuListing,
)
from models.enums import (
    FangguoFulfillmentStatus,
    IntegrationDirection,
    IntegrationProvider,
    IntegrationRunStatus,
    SalesOrderStatus,
    ShipmentStatus,
    ValidationStatus,
)


class FangguoOrderReader(Protocol):
    async def list_order_tids(self, request: FangguoTidListRequest) -> FangguoTidPage: ...

    async def get_order_detail(self, tid: str) -> FangguoOrderDetail: ...


class FangguoOrderSyncError(RuntimeError):
    pass


class FangguoOrderSyncService:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        client: FangguoOrderReader,
        *,
        platform_type: int = 225,
        page_size: int = 100,
        rolling_lookback_minutes: int = 180,
    ) -> None:
        self.session_factory = session_factory
        self.client = client
        self.platform_type = platform_type
        self.page_size = page_size
        self.rolling_lookback_minutes = rolling_lookback_minutes

    async def run(
        self,
        *,
        store_code: str,
        start_time: datetime,
        end_time: datetime,
        connection_name: str = "merchant-api",
        factory_id: int | None = None,
        shop_id: int | None = None,
        order_status: int | None = None,
        commit: bool,
    ) -> dict[str, Any]:
        normalized_store = store_code.strip().upper()
        if not normalized_store:
            raise FangguoOrderSyncError("store_code cannot be blank")
        if start_time.tzinfo is None or end_time.tzinfo is None:
            raise FangguoOrderSyncError("start_time and end_time must include a UTC offset")
        if end_time < start_time:
            raise FangguoOrderSyncError("end_time must not be earlier than start_time")

        store_id, connection_id = await self._resolve_connection(normalized_store, connection_name)
        started_at = datetime.now(UTC)
        start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)
        details = await self._fetch_details(
            start_ms=start_ms,
            end_ms=end_ms,
            factory_id=factory_id,
            shop_id=shop_id,
            order_status=order_status,
        )

        async with self.session_factory() as session:
            if commit:
                async with session.begin():
                    return await self._persist(
                        session,
                        store_id=store_id,
                        store_code=normalized_store,
                        connection_id=connection_id,
                        details=details,
                        started_at=started_at,
                        start_time=start_time,
                        end_time=end_time,
                        start_ms=start_ms,
                        end_ms=end_ms,
                    )
            return await self._preview(
                session,
                connection_id=connection_id,
                details=details,
                start_time=start_time,
                end_time=end_time,
            )

    async def _resolve_connection(self, store_code: str, connection_name: str) -> tuple[Any, Any]:
        async with self.session_factory() as session:
            row = (
                await session.execute(
                    select(Store.id, IntegrationConnection.id)
                    .join(IntegrationConnection, IntegrationConnection.store_id == Store.id)
                    .where(
                        Store.store_code == store_code,
                        IntegrationConnection.provider == IntegrationProvider.FANGGUO,
                        IntegrationConnection.connection_name == connection_name,
                    )
                )
            ).one_or_none()
        if row is None:
            raise FangguoOrderSyncError(
                f"Fangguo connection {connection_name!r} is not configured for {store_code}"
            )
        return row[0], row[1]

    async def _fetch_details(
        self,
        *,
        start_ms: int,
        end_ms: int,
        factory_id: int | None,
        shop_id: int | None,
        order_status: int | None,
    ) -> list[FangguoOrderDetail]:
        tids: list[str] = []
        seen: set[str] = set()
        page_no = 1
        while True:
            page = await self.client.list_order_tids(
                FangguoTidListRequest(
                    factory_id=factory_id,
                    shop_id=shop_id,
                    start_time=start_ms,
                    end_time=end_ms,
                    order_status=order_status,
                    platform_type=self.platform_type,
                    page_no=page_no,
                    page_size=self.page_size,
                )
            )
            new_count = 0
            for row in page.items:
                tid = row.tid.strip()
                if tid and tid not in seen:
                    seen.add(tid)
                    tids.append(tid)
                    new_count += 1
            if not page.items or len(tids) >= page.total:
                break
            if new_count == 0:
                raise FangguoOrderSyncError("Fangguo order pagination repeated without progress")
            page_no += 1
            if page_no > 10_000:
                raise FangguoOrderSyncError("Fangguo order pagination exceeded safety limit")
        return [await self.client.get_order_detail(tid) for tid in tids]

    @staticmethod
    async def _preview(
        session: AsyncSession,
        *,
        connection_id: Any,
        details: Sequence[FangguoOrderDetail],
        start_time: datetime,
        end_time: datetime,
    ) -> dict[str, Any]:
        tids = [detail.tid for detail in details]
        existing = set(
            await session.scalars(
                select(SalesOrder.external_order_id).where(
                    SalesOrder.source_connection_id == connection_id,
                    SalesOrder.external_order_id.in_(tids),
                )
            )
        )
        return {
            "orders_read": len(details),
            "items_read": sum(len(detail.items) for detail in details),
            "inserted_orders": sum(detail.tid not in existing for detail in details),
            "updated_orders": sum(detail.tid in existing for detail in details),
            "inserted_items": 0,
            "updated_items": 0,
            "matched_items": 0,
            "review_items": 0,
            "shipments_upserted": 0,
            "window_start": start_time.isoformat(),
            "window_end": end_time.isoformat(),
            "committed": False,
        }

    async def _persist(
        self,
        session: AsyncSession,
        *,
        store_id: Any,
        store_code: str,
        connection_id: Any,
        details: Sequence[FangguoOrderDetail],
        started_at: datetime,
        start_time: datetime,
        end_time: datetime,
        start_ms: int,
        end_ms: int,
    ) -> dict[str, Any]:
        synced_at = datetime.now(UTC)
        result: dict[str, Any] = {
            "orders_read": len(details),
            "items_read": sum(len(detail.items) for detail in details),
            "inserted_orders": 0,
            "updated_orders": 0,
            "inserted_items": 0,
            "updated_items": 0,
            "matched_items": 0,
            "review_items": 0,
            "shipments_upserted": 0,
            "window_start": start_time.isoformat(),
            "window_end": end_time.isoformat(),
            "committed": True,
        }
        for detail in details:
            order = await session.scalar(
                select(SalesOrder).where(
                    SalesOrder.source_connection_id == connection_id,
                    SalesOrder.external_order_id == detail.tid,
                )
            )
            order_values = _order_values(
                detail,
                store_id=store_id,
                connection_id=connection_id,
                synced_at=synced_at,
            )
            if order is None:
                order = SalesOrder(**order_values)
                session.add(order)
                await session.flush()
                result["inserted_orders"] += 1
            else:
                changed = _apply_changed_values(order, order_values, ignored={"last_synced_at"})
                order.last_synced_at = synced_at
                result["updated_orders"] += int(changed)

            await self._upsert_fulfillment(
                session,
                order=order,
                connection_id=connection_id,
                detail=detail,
                synced_at=synced_at,
            )
            for index, item in enumerate(detail.items, start=1):
                persisted_item, inserted, updated, matched = await self._upsert_item(
                    session,
                    order=order,
                    store_code=store_code,
                    detail=detail,
                    item=item,
                    index=index,
                )
                result["inserted_items"] += int(inserted)
                result["updated_items"] += int(updated)
                result["matched_items"] += int(matched)
                result["review_items"] += int(not matched)
                if await self._upsert_shipment(
                    session,
                    order=order,
                    persisted_item=persisted_item,
                    item=item,
                    synced_at=synced_at,
                ):
                    result["shipments_upserted"] += 1

        correlation_id = uuid.uuid4()
        session.add(
            IntegrationRun(
                connection_id=connection_id,
                correlation_id=correlation_id,
                idempotency_key=f"fangguo-order-sync:{correlation_id}",
                run_type="FANGGUO_ORDER_WINDOW_SYNC",
                resource_type="SALES_ORDERS",
                direction=IntegrationDirection.INBOUND,
                status=IntegrationRunStatus.SUCCEEDED,
                started_at=started_at,
                completed_at=synced_at,
                records_read=result["orders_read"],
                records_written=(
                    result["inserted_orders"]
                    + result["updated_orders"]
                    + result["inserted_items"]
                    + result["updated_items"]
                ),
                records_failed=0,
                summary=result,
            )
        )
        cursor = await session.scalar(
            select(IntegrationSyncCursor).where(
                IntegrationSyncCursor.connection_id == connection_id,
                IntegrationSyncCursor.resource_type == "SALES_ORDERS",
                IntegrationSyncCursor.cursor_name == "PAYMENT_WINDOW_END",
            )
        )
        cursor_values = {
            "cursor_value": str(end_ms),
            "watermark_at": end_time,
            "last_successful_run_at": synced_at,
            "extra_data": {
                "start_time_ms": start_ms,
                "end_time_ms": end_ms,
                "rolling_lookback_minutes": self.rolling_lookback_minutes,
                "filter_basis": "PAYMENT_TIME",
            },
        }
        if cursor is None:
            session.add(
                IntegrationSyncCursor(
                    connection_id=connection_id,
                    resource_type="SALES_ORDERS",
                    cursor_name="PAYMENT_WINDOW_END",
                    **cursor_values,
                )
            )
        else:
            _apply_changed_values(cursor, cursor_values)
        return result

    @staticmethod
    async def _upsert_fulfillment(
        session: AsyncSession,
        *,
        order: SalesOrder,
        connection_id: Any,
        detail: FangguoOrderDetail,
        synced_at: datetime,
    ) -> None:
        fulfillment = await session.scalar(
            select(FulfillmentOrder).where(FulfillmentOrder.sales_order_id == order.id)
        )
        values = {
            "source_connection_id": connection_id,
            "external_fulfillment_id": detail.id,
            "factory_external_id": str(detail.factory_id)
            if detail.factory_id is not None
            else None,
            "status": _fulfillment_status(detail.fulfillment_status),
            "external_status_code": detail.fulfillment_status,
            "external_status_description": detail.external_status_description,
            "last_synced_at": synced_at,
            "raw_payload": {
                "provider_record_id": detail.id,
                "factory_id": detail.factory_id,
                "df_status": detail.fulfillment_status,
            },
        }
        if fulfillment is None:
            session.add(FulfillmentOrder(sales_order_id=order.id, **values))
        else:
            _apply_changed_values(fulfillment, values)

    @staticmethod
    async def _upsert_item(
        session: AsyncSession,
        *,
        order: SalesOrder,
        store_code: str,
        detail: FangguoOrderDetail,
        item: FangguoOrderItem,
        index: int,
    ) -> tuple[SalesOrderItem, bool, bool, bool]:
        if item.quantity <= 0:
            raise FangguoOrderSyncError(
                f"Order {detail.tid} contains non-positive quantity at item {index}"
            )
        external_line_id = item.oid or item.sys_oid or item.id or f"{detail.tid}:{index}"
        existing = await session.scalar(
            select(SalesOrderItem).where(
                SalesOrderItem.sales_order_id == order.id,
                SalesOrderItem.external_line_id == external_line_id,
            )
        )
        sku, listing = await _resolve_sku(session, store_code=store_code, item=item)
        matched = sku is not None
        values = {
            "sku_id": sku.id if sku is not None else None,
            "temu_listing_id": listing.id if listing is not None else None,
            "provider_item_id": item.id,
            "external_sku_id": item.original_sku_id or None,
            "external_goods_id": item.original_goods_id or None,
            "seller_sku": item.outer_iid or None,
            "mapped_sku": item.shop_mapping_sku or None,
            "title": item.title,
            "specification": item.sku_properties_name,
            "quantity": item.quantity,
            "unit_price": item.price,
            "currency": "USD",
            "match_status": (ValidationStatus.VALID if matched else ValidationStatus.MANUAL_REVIEW),
            "refund_status_description": item.refund_status_description,
            "cancelled": item.cancelled,
            "raw_payload": {
                "provider_item_id": item.id,
                "external_line_id": external_line_id,
                "original_sku_id": item.original_sku_id,
                "original_goods_id": item.original_goods_id,
                "seller_sku": item.outer_iid,
                "mapped_sku": item.shop_mapping_sku,
            },
        }
        if existing is None:
            existing = SalesOrderItem(
                sales_order_id=order.id,
                external_line_id=external_line_id,
                **values,
            )
            session.add(existing)
            await session.flush()
            return existing, True, False, matched
        changed = _apply_changed_values(existing, values)
        return existing, False, changed, matched

    @staticmethod
    async def _upsert_shipment(
        session: AsyncSession,
        *,
        order: SalesOrder,
        persisted_item: SalesOrderItem,
        item: FangguoOrderItem,
        synced_at: datetime,
    ) -> bool:
        carrier = (item.logistics_company_code or "").strip()
        tracking = (item.logistics_order_number or "").strip()
        if not carrier or not tracking:
            return False
        shipment = await session.scalar(
            select(SalesOrderShipment).where(
                SalesOrderShipment.sales_order_id == order.id,
                SalesOrderShipment.carrier_code == carrier,
                SalesOrderShipment.tracking_number == tracking,
            )
        )
        values = {
            "sales_order_item_id": persisted_item.id,
            "status": ShipmentStatus.SHIPPED,
            "last_seen_at": synced_at,
            "raw_payload": {"source": "FANGGUO_ORDER_DETAIL"},
        }
        if shipment is None:
            session.add(
                SalesOrderShipment(
                    sales_order_id=order.id,
                    carrier_code=carrier,
                    tracking_number=tracking,
                    **values,
                )
            )
        else:
            _apply_changed_values(shipment, values)
        return True


async def _resolve_sku(
    session: AsyncSession,
    *,
    store_code: str,
    item: FangguoOrderItem,
) -> tuple[SKU | None, TemuListing | None]:
    candidate_codes = {
        value.strip()
        for value in (item.shop_mapping_sku, item.outer_iid)
        if value and value.strip()
    }
    sku_rows: list[SKU] = []
    if candidate_codes:
        sku_rows = list(
            await session.scalars(
                select(SKU).where(
                    (SKU.factory_sku.in_(candidate_codes)) | (SKU.temu_sku.in_(candidate_codes))
                )
            )
        )
    listing: TemuListing | None = None
    external_sku_id = (item.original_sku_id or "").strip()
    if external_sku_id:
        listing = await session.scalar(
            select(TemuListing).where(
                TemuListing.store_code == store_code,
                TemuListing.temu_sku_id == external_sku_id,
            )
        )
    matched_ids = {sku.id for sku in sku_rows}
    if listing is not None:
        matched_ids.add(listing.sku_id)
    if len(matched_ids) != 1:
        return None, None
    sku_id = next(iter(matched_ids))
    sku = next((row for row in sku_rows if row.id == sku_id), None)
    if sku is None:
        sku = await session.get(SKU, sku_id)
    if listing is None:
        listing = await session.scalar(
            select(TemuListing).where(
                TemuListing.store_code == store_code,
                TemuListing.sku_id == sku_id,
            )
        )
    return sku, listing


def _order_values(
    detail: FangguoOrderDetail,
    *,
    store_id: Any,
    connection_id: Any,
    synced_at: datetime,
) -> dict[str, Any]:
    total = sum(
        ((item.price or Decimal("0")) * item.quantity for item in detail.items),
        Decimal("0"),
    ).quantize(Decimal("0.01"))
    return {
        "store_id": store_id,
        "source_connection_id": connection_id,
        "external_order_id": detail.tid,
        "provider_record_id": detail.id,
        "system_order_id": detail.system_tid,
        "platform_code": detail.platform,
        "platform_description": detail.platform_description,
        "order_type": detail.order_type,
        "status": _sales_order_status(detail),
        "external_status_description": detail.external_status_description,
        "currency": "USD",
        "total_amount": total,
        "last_synced_at": synced_at,
        "raw_payload": {
            "provider_record_id": detail.id,
            "system_tid": detail.system_tid,
            "tid": detail.tid,
            "platform": detail.platform,
            "df_status": detail.fulfillment_status,
            "store_name": detail.store_name,
        },
    }


def _sales_order_status(detail: FangguoOrderDetail) -> SalesOrderStatus:
    description = (detail.external_status_description or "").strip()
    if "关闭" in description or (
        bool(detail.items) and all(item.cancelled for item in detail.items)
    ):
        return SalesOrderStatus.CANCELLED
    if "完成" in description:
        return SalesOrderStatus.COMPLETED
    if "已发货" in description or "部分发货" in description:
        return SalesOrderStatus.SHIPPED
    if detail.fulfillment_status in range(0, 6):
        return SalesOrderStatus.PROCESSING
    return SalesOrderStatus.UNKNOWN


def _fulfillment_status(code: int) -> FangguoFulfillmentStatus:
    return {
        0: FangguoFulfillmentStatus.WAITING_ORGANIZATION,
        1: FangguoFulfillmentStatus.WAITING_PUSH,
        2: FangguoFulfillmentStatus.REVERSED,
        3: FangguoFulfillmentStatus.FACTORY_REVIEW,
        4: FangguoFulfillmentStatus.IN_PRODUCTION,
        5: FangguoFulfillmentStatus.PACKED,
    }.get(code, FangguoFulfillmentStatus.UNKNOWN)


def _apply_changed_values(
    target: object,
    values: dict[str, Any],
    *,
    ignored: set[str] | None = None,
) -> bool:
    changed = False
    ignored = ignored or set()
    for key, value in values.items():
        if key not in ignored and getattr(target, key) != value:
            changed = True
        setattr(target, key, value)
    return changed

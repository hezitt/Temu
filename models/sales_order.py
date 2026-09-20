import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import (
    FangguoFulfillmentStatus,
    SalesOrderStatus,
    ShipmentStatus,
    ValidationStatus,
)
from models.types import string_enum


class SalesOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sales_orders"
    __table_args__ = (
        UniqueConstraint(
            "source_connection_id",
            "external_order_id",
            name="uq_sales_orders_connection_external_order",
        ),
        CheckConstraint(
            "total_amount IS NULL OR total_amount >= 0", name="total_amount_nonnegative"
        ),
    )

    store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="RESTRICT"), index=True
    )
    source_connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="RESTRICT"), index=True
    )
    external_order_id: Mapped[str] = mapped_column(String(255), index=True)
    provider_record_id: Mapped[str | None] = mapped_column(String(255), index=True)
    system_order_id: Mapped[str | None] = mapped_column(String(255), index=True)
    platform_code: Mapped[int] = mapped_column(Integer, index=True)
    platform_description: Mapped[str | None] = mapped_column(String(128))
    order_type: Mapped[int] = mapped_column(Integer)
    status: Mapped[SalesOrderStatus] = mapped_column(
        string_enum(SalesOrderStatus, "sales_order_status"),
        default=SalesOrderStatus.DISCOVERED,
        server_default=SalesOrderStatus.DISCOVERED.value,
        index=True,
    )
    external_status_description: Mapped[str | None] = mapped_column(String(128))
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )

    items = relationship("SalesOrderItem", back_populates="sales_order")
    fulfillment = relationship("FulfillmentOrder", back_populates="sales_order", uselist=False)
    shipments = relationship("SalesOrderShipment", back_populates="sales_order")


class SalesOrderItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sales_order_items"
    __table_args__ = (
        UniqueConstraint(
            "sales_order_id", "external_line_id", name="uq_sales_order_items_order_line"
        ),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price IS NULL OR unit_price >= 0", name="unit_price_nonnegative"),
    )

    sales_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sales_orders.id", ondelete="CASCADE"), index=True
    )
    sku_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("skus.id", ondelete="RESTRICT"), index=True
    )
    temu_listing_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("temu_listings.id", ondelete="RESTRICT"), index=True
    )
    external_line_id: Mapped[str] = mapped_column(String(255))
    provider_item_id: Mapped[str | None] = mapped_column(String(255), index=True)
    external_sku_id: Mapped[str | None] = mapped_column(String(255), index=True)
    external_goods_id: Mapped[str | None] = mapped_column(String(255), index=True)
    seller_sku: Mapped[str | None] = mapped_column(String(255), index=True)
    mapped_sku: Mapped[str | None] = mapped_column(String(255), index=True)
    title: Mapped[str | None] = mapped_column(String(512))
    specification: Mapped[str | None] = mapped_column(String(512))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    match_status: Mapped[ValidationStatus] = mapped_column(
        string_enum(ValidationStatus, "sales_order_item_match_status"),
        default=ValidationStatus.PENDING,
        server_default=ValidationStatus.PENDING.value,
        index=True,
    )
    refund_status_description: Mapped[str | None] = mapped_column(String(128))
    cancelled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )

    sales_order = relationship("SalesOrder", back_populates="items")


class FulfillmentOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fulfillment_orders"

    sales_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sales_orders.id", ondelete="RESTRICT"), unique=True, index=True
    )
    source_connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="RESTRICT"), index=True
    )
    external_fulfillment_id: Mapped[str] = mapped_column(String(255), index=True)
    factory_external_id: Mapped[str | None] = mapped_column(String(255), index=True)
    status: Mapped[FangguoFulfillmentStatus] = mapped_column(
        string_enum(FangguoFulfillmentStatus, "fangguo_fulfillment_status"),
        default=FangguoFulfillmentStatus.UNKNOWN,
        server_default=FangguoFulfillmentStatus.UNKNOWN.value,
        index=True,
    )
    external_status_code: Mapped[int] = mapped_column(Integer, index=True)
    external_status_description: Mapped[str | None] = mapped_column(String(128))
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )

    sales_order = relationship("SalesOrder", back_populates="fulfillment")


class SalesOrderShipment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sales_order_shipments"
    __table_args__ = (
        UniqueConstraint(
            "sales_order_id",
            "carrier_code",
            "tracking_number",
            name="uq_sales_order_shipments_order_carrier_tracking",
        ),
    )

    sales_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sales_orders.id", ondelete="RESTRICT"), index=True
    )
    sales_order_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sales_order_items.id", ondelete="SET NULL"), index=True
    )
    carrier_code: Mapped[str] = mapped_column(String(64))
    tracking_number: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[ShipmentStatus] = mapped_column(
        string_enum(ShipmentStatus, "sales_order_shipment_status"),
        default=ShipmentStatus.SHIPPED,
        server_default=ShipmentStatus.SHIPPED.value,
        index=True,
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )

    sales_order = relationship("SalesOrder", back_populates="shipments")

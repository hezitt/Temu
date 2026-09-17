import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import QuoteSource, StockOrderStatus, ValidationStatus
from models.types import string_enum


class StockOrder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stock_orders"
    __table_args__ = (
        CheckConstraint("carton_count IS NULL OR carton_count > 0", name="carton_count_positive"),
        CheckConstraint(
            "units_per_carton IS NULL OR units_per_carton > 0", name="units_per_carton_positive"
        ),
    )

    stock_order_code: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), index=True
    )
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("import_batches.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[StockOrderStatus] = mapped_column(
        string_enum(StockOrderStatus, "stock_order_status"),
        default=StockOrderStatus.IMPORTED,
        server_default=StockOrderStatus.IMPORTED.value,
        index=True,
    )
    source: Mapped[QuoteSource] = mapped_column(string_enum(QuoteSource, "stock_order_source"))
    delivery_due_date: Mapped[date | None] = mapped_column(Date)
    carton_count: Mapped[int | None] = mapped_column(Integer)
    units_per_carton: Mapped[int | None] = mapped_column(Integer)
    supplier_workbook_path: Mapped[str | None] = mapped_column(String(1024))
    print_package_path: Mapped[str | None] = mapped_column(String(1024))
    validation_report_path: Mapped[str | None] = mapped_column(String(1024))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    extra_data: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )

    supplier = relationship("Supplier", back_populates="stock_orders")
    items = relationship("StockOrderItem", back_populates="stock_order")
    labels = relationship("Label", back_populates="stock_order")
    shipments = relationship("Shipment", back_populates="stock_order")


class StockOrderItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stock_order_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["sku_id", "design_id"],
            ["skus.id", "skus.design_id"],
            ondelete="RESTRICT",
            name="fk_stock_order_items_sku_design_skus",
        ),
        UniqueConstraint("stock_order_id", "line_number", name="uq_stock_order_items_order_line"),
        CheckConstraint(
            "(sku_id IS NULL AND design_id IS NULL) OR "
            "(sku_id IS NOT NULL AND design_id IS NOT NULL)",
            name="sku_design_pair",
        ),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint(
            "units_per_carton IS NULL OR units_per_carton > 0", name="units_per_carton_positive"
        ),
        CheckConstraint("carton_count IS NULL OR carton_count > 0", name="carton_count_positive"),
    )

    stock_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stock_orders.id", ondelete="CASCADE"), index=True
    )
    line_number: Mapped[int] = mapped_column(Integer)
    source_temu_sku: Mapped[str] = mapped_column(String(128), index=True)
    sku_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    design_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    factory_sku_snapshot: Mapped[str | None] = mapped_column(String(128))
    design_code_snapshot: Mapped[str | None] = mapped_column(String(64))
    temu_sku_snapshot: Mapped[str | None] = mapped_column(String(128))
    quantity: Mapped[int] = mapped_column(Integer)
    units_per_carton: Mapped[int | None] = mapped_column(Integer)
    carton_count: Mapped[int | None] = mapped_column(Integer)
    image_filename: Mapped[str | None] = mapped_column(String(512))
    match_status: Mapped[ValidationStatus] = mapped_column(
        string_enum(ValidationStatus, "stock_item_match_status"),
        default=ValidationStatus.PENDING,
        server_default=ValidationStatus.PENDING.value,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text)

    stock_order = relationship("StockOrder", back_populates="items")
    labels = relationship("Label", back_populates="stock_order_item")

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import CostCompletenessStatus, ValidationStatus
from models.types import string_enum


class FactoryCost(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "factory_costs"
    __table_args__ = (
        UniqueConstraint(
            "supplier_id",
            "product_type",
            "colors_count",
            "width_cm",
            "height_cm",
            "framed",
            "effective_from",
            name="uq_factory_costs_supplier_variant_effective",
        ),
        CheckConstraint("width_cm > 0", name="width_cm_positive"),
        CheckConstraint("height_cm > 0", name="height_cm_positive"),
        CheckConstraint("colors_count > 0", name="colors_count_positive"),
        CheckConstraint("base_product_cost >= 0", name="base_product_cost_nonnegative"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="effective_date_order",
        ),
    )

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), index=True
    )
    sku_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("skus.id", ondelete="SET NULL"), index=True
    )
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("import_batches.id", ondelete="SET NULL"), index=True
    )
    product_type: Mapped[str] = mapped_column(
        String(64), default="PAINT_BY_NUMBERS", server_default="PAINT_BY_NUMBERS"
    )
    colors_count: Mapped[int] = mapped_column(Integer)
    source_size_label: Mapped[str] = mapped_column(String(128))
    size_code: Mapped[str] = mapped_column(String(32))
    width_cm: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    height_cm: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    framed: Mapped[bool]
    base_product_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    customization_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    label_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    packaging_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    domestic_shipping_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    other_variable_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    total_variable_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="CNY", server_default="CNY")
    shipping_included: Mapped[bool] = mapped_column(default=False, server_default="false")
    effective_from: Mapped[date] = mapped_column(Date, index=True)
    effective_to: Mapped[date | None] = mapped_column(Date)
    validation_status: Mapped[ValidationStatus] = mapped_column(
        string_enum(ValidationStatus, "factory_cost_validation_status"),
        default=ValidationStatus.PENDING,
        server_default=ValidationStatus.PENDING.value,
        index=True,
    )
    cost_completeness_status: Mapped[CostCompletenessStatus] = mapped_column(
        string_enum(CostCompletenessStatus, "cost_completeness_status"),
        default=CostCompletenessStatus.INCOMPLETE,
        server_default=CostCompletenessStatus.INCOMPLETE.value,
        index=True,
    )
    source_sheet: Mapped[str | None] = mapped_column(String(255))
    source_row: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )

    supplier = relationship("Supplier", back_populates="factory_costs")
    sku = relationship("SKU", back_populates="factory_costs", foreign_keys=[sku_id])

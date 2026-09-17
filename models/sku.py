import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SKU(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "skus"
    __table_args__ = (
        ForeignKeyConstraint(
            ["product_id", "design_id"],
            ["products.id", "products.design_id"],
            ondelete="RESTRICT",
            name="fk_skus_product_design_products",
        ),
        UniqueConstraint("id", "design_id", name="uq_skus_id_design_id"),
        UniqueConstraint("supplier_id", "factory_sku", name="uq_skus_supplier_factory_sku"),
        UniqueConstraint(
            "supplier_id",
            "design_id",
            "width_cm",
            "height_cm",
            "colors_count",
            "framed",
            name="uq_skus_supplier_design_variant",
        ),
        CheckConstraint("width_cm > 0", name="width_cm_positive"),
        CheckConstraint("height_cm > 0", name="height_cm_positive"),
        CheckConstraint("colors_count > 0", name="colors_count_positive"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(index=True)
    design_id: Mapped[uuid.UUID] = mapped_column(index=True)
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), index=True
    )
    factory_sku: Mapped[str] = mapped_column(String(128), index=True)
    temu_sku: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    size_label: Mapped[str] = mapped_column(String(64))
    width_cm: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    height_cm: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    colors_count: Mapped[int] = mapped_column(Integer, index=True)
    framed: Mapped[bool] = mapped_column(Boolean, index=True)
    image_path: Mapped[str | None] = mapped_column(String(1024))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    resolved_factory_cost_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    shipping_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    shipping_cost_type: Mapped[str | None] = mapped_column(String(32))
    exchange_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    exchange_rate_source: Mapped[str | None] = mapped_column(String(32))
    exchange_rate_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unit_variable_cost_cny: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    label_service_cost_cny: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    label_service_cost_status: Mapped[str | None] = mapped_column(String(32))

    product = relationship("Product", back_populates="skus")
    supplier = relationship("Supplier", back_populates="skus")
    factory_costs = relationship(
        "FactoryCost", back_populates="sku", foreign_keys="FactoryCost.sku_id"
    )
    temu_listings = relationship("TemuListing", back_populates="sku")

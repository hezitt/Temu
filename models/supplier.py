from typing import Any

from sqlalchemy import JSON, Boolean, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Supplier(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "suppliers"

    supplier_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    country_code: Mapped[str] = mapped_column(String(2), default="US")
    currency: Mapped[str] = mapped_column(String(3), default="CNY", server_default="CNY")
    timezone: Mapped[str] = mapped_column(String(64), default="America/Los_Angeles")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    contact: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )
    extra_data: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )

    skus = relationship("SKU", back_populates="supplier")
    factory_costs = relationship("FactoryCost", back_populates="supplier")
    stock_orders = relationship("StockOrder", back_populates="supplier")

import uuid
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import ProductStatus
from models.types import string_enum


class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("id", "design_id", name="uq_products_id_design_id"),
        UniqueConstraint("design_id", name="uq_products_design_id"),
    )

    design_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("designs.id", ondelete="RESTRICT"), index=True
    )
    internal_product_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(512))
    status: Mapped[ProductStatus] = mapped_column(
        string_enum(ProductStatus, "product_status"),
        default=ProductStatus.DRAFT,
        server_default=ProductStatus.DRAFT.value,
        index=True,
    )
    extra_data: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )

    design = relationship("Design", back_populates="products")
    skus = relationship("SKU", back_populates="product")

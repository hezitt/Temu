import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import ImportRowStatus
from models.types import string_enum


class FactoryQuoteRow(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Immutable row-level evidence for every parsed quote candidate."""

    __tablename__ = "factory_quote_rows"
    __table_args__ = (
        UniqueConstraint(
            "import_batch_id",
            "source_sheet",
            "source_row",
            "variant_type",
            name="uq_factory_quote_rows_batch_source_variant",
        ),
        CheckConstraint(
            "(width_cm IS NULL AND height_cm IS NULL) OR "
            "(width_cm IS NOT NULL AND height_cm IS NOT NULL)",
            name="dimension_pair",
        ),
        CheckConstraint("unit_cost IS NULL OR unit_cost >= 0", name="unit_cost_nonnegative"),
    )

    import_batch_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("import_batches.id", ondelete="CASCADE"), index=True
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"), index=True
    )
    source_sheet: Mapped[str] = mapped_column(String(255))
    source_row: Mapped[int] = mapped_column(Integer)
    source_column: Mapped[str] = mapped_column(String(16))
    product_type: Mapped[str] = mapped_column(String(64))
    variant_type: Mapped[str] = mapped_column(String(16))
    raw_color: Mapped[str | None] = mapped_column(String(128))
    raw_size: Mapped[str | None] = mapped_column(String(256))
    raw_cost: Mapped[str | None] = mapped_column(String(128))
    colors_count: Mapped[int | None] = mapped_column(Integer)
    size_code: Mapped[str | None] = mapped_column(String(32))
    width_cm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3))
    shipping_included: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    row_status: Mapped[ImportRowStatus] = mapped_column(
        string_enum(ImportRowStatus, "factory_quote_row_status"), index=True
    )
    issues: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=list
    )
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )

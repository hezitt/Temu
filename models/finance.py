import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import FinancialTransactionType, QuoteSource, ValidationStatus
from models.types import string_enum


class FinancialTransaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "financial_transactions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["sku_id", "design_id"],
            ["skus.id", "skus.design_id"],
            ondelete="RESTRICT",
            name="fk_financial_transactions_sku_design_skus",
        ),
        CheckConstraint(
            "(sku_id IS NULL AND design_id IS NULL) OR "
            "(sku_id IS NOT NULL AND design_id IS NOT NULL)",
            name="sku_design_pair",
        ),
    )

    sku_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    design_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    temu_listing_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("temu_listings.id", ondelete="SET NULL"), index=True
    )
    stock_order_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("stock_order_items.id", ondelete="SET NULL"), index=True
    )
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("import_batches.id", ondelete="SET NULL"), index=True
    )
    transaction_type: Mapped[FinancialTransactionType] = mapped_column(
        string_enum(FinancialTransactionType, "financial_transaction_type"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    settlement_reference: Mapped[str | None] = mapped_column(String(128), index=True)
    external_reference: Mapped[str | None] = mapped_column(String(256), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    source: Mapped[QuoteSource] = mapped_column(string_enum(QuoteSource, "finance_source"))
    match_status: Mapped[ValidationStatus] = mapped_column(
        string_enum(ValidationStatus, "finance_match_status"),
        default=ValidationStatus.PENDING,
        server_default=ValidationStatus.PENDING.value,
        index=True,
    )
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )

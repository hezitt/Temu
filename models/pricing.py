import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import ExecutionStatus, PricingDecisionType, QuoteSource
from models.types import string_enum


class PricingRuleSet(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pricing_rule_sets"
    __table_args__ = (
        UniqueConstraint("rule_code", "version", name="uq_pricing_rule_sets_code_version"),
        CheckConstraint("min_margin >= 0 AND min_margin < 1", name="min_margin_range"),
        CheckConstraint("target_margin > min_margin AND target_margin < 1", name="margin_order"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="effective_date_order",
        ),
    )

    rule_code: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int]
    min_margin: Mapped[Decimal] = mapped_column(Numeric(8, 6))
    target_margin: Mapped[Decimal] = mapped_column(Numeric(8, 6))
    negotiation_strategy: Mapped[str] = mapped_column(String(128), default="minimum_target_margin")
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", index=True
    )
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    configuration: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )


class PricingQuote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pricing_quotes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["listing_id", "sku_id"],
            ["temu_listings.id", "temu_listings.sku_id"],
            ondelete="RESTRICT",
            name="fk_pricing_quotes_listing_sku_temu_listings",
        ),
        UniqueConstraint(
            "listing_id", "external_quote_id", name="uq_pricing_quotes_listing_external_quote"
        ),
        UniqueConstraint("id", "sku_id", name="uq_pricing_quotes_id_sku_id"),
        CheckConstraint("quote_price > 0", name="quote_price_positive"),
    )

    listing_id: Mapped[uuid.UUID] = mapped_column(index=True)
    sku_id: Mapped[uuid.UUID] = mapped_column(index=True)
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("import_batches.id", ondelete="SET NULL"), index=True
    )
    external_quote_id: Mapped[str | None] = mapped_column(String(128))
    quote_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3))
    source: Mapped[QuoteSource] = mapped_column(string_enum(QuoteSource, "quote_source"))
    quoted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )

    listing = relationship("TemuListing", back_populates="pricing_quotes")
    decisions = relationship("PricingDecision", back_populates="quote")


class PricingDecision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "pricing_decisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["quote_id", "sku_id"],
            ["pricing_quotes.id", "pricing_quotes.sku_id"],
            ondelete="RESTRICT",
            name="fk_pricing_decisions_quote_sku_pricing_quotes",
        ),
        CheckConstraint("quote_price_snapshot > 0", name="quote_price_positive"),
        CheckConstraint(
            "variable_cost_snapshot IS NULL OR variable_cost_snapshot >= 0",
            name="variable_cost_nonnegative",
        ),
        CheckConstraint("gross_margin IS NULL OR gross_margin < 1", name="gross_margin_range"),
        CheckConstraint("min_margin >= 0 AND min_margin < 1", name="min_margin_range"),
        CheckConstraint("target_margin > min_margin AND target_margin < 1", name="margin_order"),
    )

    quote_id: Mapped[uuid.UUID] = mapped_column(index=True)
    sku_id: Mapped[uuid.UUID] = mapped_column(index=True)
    factory_cost_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("factory_costs.id", ondelete="RESTRICT"), index=True
    )
    pricing_rule_set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pricing_rule_sets.id", ondelete="RESTRICT"), index=True
    )
    quote_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    variable_cost_snapshot: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3))
    gross_margin: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    min_margin: Mapped[Decimal] = mapped_column(Numeric(8, 6))
    target_margin: Mapped[Decimal] = mapped_column(Numeric(8, 6))
    minimum_acceptable_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    decision: Mapped[PricingDecisionType] = mapped_column(
        string_enum(PricingDecisionType, "pricing_decision_type"), index=True
    )
    negotiation_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    reason: Mapped[str | None] = mapped_column(Text)
    rule_version_snapshot: Mapped[str] = mapped_column(String(64))
    is_dry_run: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    execution_adapter: Mapped[str | None] = mapped_column(String(128))
    execution_status: Mapped[ExecutionStatus] = mapped_column(
        string_enum(ExecutionStatus, "pricing_execution_status"),
        default=ExecutionStatus.NOT_REQUESTED,
        server_default=ExecutionStatus.NOT_REQUESTED.value,
        index=True,
    )
    execution_result: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )
    execution_error: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    quote = relationship("PricingQuote", back_populates="decisions")

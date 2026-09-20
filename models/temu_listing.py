import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import ListingStatus
from models.types import string_enum


class TemuListing(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "temu_listings"
    __table_args__ = (
        UniqueConstraint("store_code", "sku_id", name="uq_temu_listings_store_sku"),
        UniqueConstraint("store_code", "temu_goods_id", name="uq_temu_listings_store_goods"),
        UniqueConstraint(
            "store_code", "temu_sku_id", name="uq_temu_listings_store_temu_sku_id"
        ),
        UniqueConstraint("store_code", "temu_spu", "sku_id", name="uq_temu_listings_store_spu_sku"),
        UniqueConstraint("id", "sku_id", name="uq_temu_listings_id_sku_id"),
    )

    sku_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("skus.id", ondelete="RESTRICT"), index=True
    )
    store_code: Mapped[str] = mapped_column(String(64), index=True)
    marketplace: Mapped[str] = mapped_column(String(16), default="US", server_default="US")
    dianxiaomi_spu_id: Mapped[str | None] = mapped_column(String(128), index=True)
    temu_spu: Mapped[str | None] = mapped_column(String(128), index=True)
    temu_skc_id: Mapped[str | None] = mapped_column(String(128), index=True)
    temu_sku_id: Mapped[str | None] = mapped_column(String(128), index=True)
    temu_goods_id: Mapped[str | None] = mapped_column(String(128), index=True)
    platform_review_status: Mapped[str | None] = mapped_column(String(32), index=True)
    platform_lifecycle_status: Mapped[str | None] = mapped_column(String(64))
    external_id_source: Mapped[str | None] = mapped_column(String(32))
    external_id_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[ListingStatus] = mapped_column(
        string_enum(ListingStatus, "listing_status"),
        default=ListingStatus.DRAFT,
        server_default=ListingStatus.DRAFT.value,
        index=True,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )

    sku = relationship("SKU", back_populates="temu_listings")
    pricing_quotes = relationship("PricingQuote", back_populates="listing")

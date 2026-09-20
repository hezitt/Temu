import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import PlatformAssetStatus
from models.types import string_enum


class PlatformAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "platform_assets"
    __table_args__ = (
        CheckConstraint("byte_size IS NULL OR byte_size >= 0", name="byte_size_nonnegative"),
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="RESTRICT"), index=True
    )
    design_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("designs.id", ondelete="RESTRICT"), index=True
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    sku_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("skus.id", ondelete="RESTRICT"), index=True
    )
    asset_role: Mapped[str] = mapped_column(String(64), index=True)
    local_path: Mapped[str] = mapped_column(String(1024))
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    content_type: Mapped[str | None] = mapped_column(String(128))
    byte_size: Mapped[int | None] = mapped_column(Integer)
    external_asset_id: Mapped[str | None] = mapped_column(String(255), index=True)
    status: Mapped[PlatformAssetStatus] = mapped_column(
        string_enum(PlatformAssetStatus, "platform_asset_status"),
        default=PlatformAssetStatus.PENDING,
        server_default=PlatformAssetStatus.PENDING.value,
        index=True,
    )
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )

    connection = relationship("IntegrationConnection", back_populates="assets")

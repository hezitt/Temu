from typing import Any

from sqlalchemy import JSON, Boolean, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Store(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "stores"
    __table_args__ = (UniqueConstraint("platform", "mall_id", name="uq_stores_platform_mall_id"),)

    store_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255))
    platform: Mapped[str] = mapped_column(String(32), default="TEMU", server_default="TEMU")
    marketplace: Mapped[str] = mapped_column(String(16), default="US", server_default="US")
    seller_type: Mapped[str] = mapped_column(
        String(32), default="CROSS_BORDER", server_default="CROSS_BORDER"
    )
    business_model: Mapped[str] = mapped_column(
        String(32), default="SEMI_MANAGED", server_default="SEMI_MANAGED"
    )
    mall_id: Mapped[str | None] = mapped_column(String(128), index=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    timezone: Mapped[str] = mapped_column(
        String(64), default="America/Los_Angeles", server_default="America/Los_Angeles"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    extra_data: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )

    integration_connections = relationship("IntegrationConnection", back_populates="store")

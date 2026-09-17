from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Design(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "designs"

    design_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    factory_design_code: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255))
    theme: Mapped[str | None] = mapped_column(String(128), index=True)
    sub_theme: Mapped[str | None] = mapped_column(String(128), index=True)
    image_path: Mapped[str | None] = mapped_column(String(1024))
    additional_image_paths: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=list
    )
    line_art_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    line_art_cost_currency: Mapped[str | None] = mapped_column(String(3))
    line_art_cost_paid: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    line_art_cost_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    line_art_reusable: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    is_customizable: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    requires_manual_review: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    special_handling_notes: Mapped[str | None] = mapped_column(Text)
    extra_data: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )

    products = relationship("Product", back_populates="design")

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import ShipmentStatus
from models.types import string_enum


class Shipment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "shipments"
    __table_args__ = (
        UniqueConstraint("carrier", "tracking_number", name="uq_shipments_carrier_tracking"),
        CheckConstraint("carton_count > 0", name="carton_count_positive"),
    )

    stock_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stock_orders.id", ondelete="RESTRICT"), index=True
    )
    shipment_code: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    carrier: Mapped[str] = mapped_column(String(64))
    tracking_number: Mapped[str] = mapped_column(String(128))
    status: Mapped[ShipmentStatus] = mapped_column(
        string_enum(ShipmentStatus, "shipment_status"),
        default=ShipmentStatus.READY_FOR_SHIPMENT,
        server_default=ShipmentStatus.READY_FOR_SHIPMENT.value,
        index=True,
    )
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    carton_count: Mapped[int] = mapped_column(Integer)
    manually_recorded_by: Mapped[str] = mapped_column(String(128))
    extra_data: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )

    stock_order = relationship("StockOrder", back_populates="shipments")

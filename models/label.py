import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import LabelStatus, LabelType
from models.types import string_enum


class Label(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "labels"
    __table_args__ = (
        ForeignKeyConstraint(
            ["sku_id", "design_id"],
            ["skus.id", "skus.design_id"],
            ondelete="RESTRICT",
            name="fk_labels_sku_design_skus",
        ),
        UniqueConstraint(
            "stock_order_item_id", "label_type", "version", name="uq_labels_item_type_version"
        ),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint("required_quantity >= 0", name="required_quantity_nonnegative"),
        CheckConstraint("planned_print_quantity >= 0", name="planned_print_quantity_nonnegative"),
    )

    stock_order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stock_orders.id", ondelete="CASCADE"), index=True
    )
    stock_order_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stock_order_items.id", ondelete="CASCADE"), index=True
    )
    sku_id: Mapped[uuid.UUID] = mapped_column(index=True)
    design_id: Mapped[uuid.UUID] = mapped_column(index=True)
    label_type: Mapped[LabelType] = mapped_column(string_enum(LabelType, "label_type"), index=True)
    status: Mapped[LabelStatus] = mapped_column(
        string_enum(LabelStatus, "label_status"),
        default=LabelStatus.WAITING_LABEL,
        server_default=LabelStatus.WAITING_LABEL.value,
        index=True,
    )
    file_path: Mapped[str | None] = mapped_column(String(1024))
    original_file_path: Mapped[str | None] = mapped_column(String(1024))
    media_type: Mapped[str | None] = mapped_column(String(128))
    page_size: Mapped[str | None] = mapped_column(String(64))
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    required_quantity: Mapped[int] = mapped_column(Integer)
    planned_print_quantity: Mapped[int] = mapped_column(Integer)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    printed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    stock_order = relationship("StockOrder", back_populates="labels")
    stock_order_item = relationship("StockOrderItem", back_populates="labels")

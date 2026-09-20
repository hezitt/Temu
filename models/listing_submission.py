import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import ListingSubmissionAction, ListingSubmissionStatus
from models.types import string_enum


class ListingSubmission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "listing_submissions"
    __table_args__ = (CheckConstraint("attempt_count > 0", name="attempt_count_positive"),)

    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="RESTRICT"), index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    sku_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("skus.id", ondelete="RESTRICT"), index=True
    )
    temu_listing_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("temu_listings.id", ondelete="RESTRICT"), index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    action: Mapped[ListingSubmissionAction] = mapped_column(
        string_enum(ListingSubmissionAction, "listing_submission_action"), index=True
    )
    status: Mapped[ListingSubmissionStatus] = mapped_column(
        string_enum(ListingSubmissionStatus, "listing_submission_status"),
        default=ListingSubmissionStatus.PENDING,
        server_default=ListingSubmissionStatus.PENDING.value,
        index=True,
    )
    is_dry_run: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    attempt_count: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    provider_request_id: Mapped[str | None] = mapped_column(String(255), index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    request_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )
    response_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )
    error_message: Mapped[str | None] = mapped_column(Text)

    connection = relationship("IntegrationConnection", back_populates="listing_submissions")

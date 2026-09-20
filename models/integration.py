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
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import (
    IntegrationConnectionStatus,
    IntegrationDirection,
    IntegrationEventStatus,
    IntegrationProvider,
    IntegrationRunStatus,
)
from models.types import string_enum


class IntegrationConnection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "integration_connections"
    __table_args__ = (
        UniqueConstraint(
            "store_id",
            "provider",
            "connection_name",
            name="uq_integration_connections_store_provider_name",
        ),
    )

    store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="RESTRICT"), index=True
    )
    provider: Mapped[IntegrationProvider] = mapped_column(
        string_enum(IntegrationProvider, "integration_provider"), index=True
    )
    connection_name: Mapped[str] = mapped_column(String(128), default="default")
    external_account_id: Mapped[str | None] = mapped_column(String(128), index=True)
    status: Mapped[IntegrationConnectionStatus] = mapped_column(
        string_enum(IntegrationConnectionStatus, "integration_connection_status"),
        default=IntegrationConnectionStatus.PENDING_AUTHORIZATION,
        server_default=IntegrationConnectionStatus.PENDING_AUTHORIZATION.value,
        index=True,
    )
    credential_reference: Mapped[str | None] = mapped_column(String(512))
    token_fingerprint: Mapped[str | None] = mapped_column(String(64))
    scopes: Mapped[list[str]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=list
    )
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    extra_data: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )

    store = relationship("Store", back_populates="integration_connections")
    sync_cursors = relationship("IntegrationSyncCursor", back_populates="connection")
    runs = relationship("IntegrationRun", back_populates="connection")
    events = relationship("PlatformEvent", back_populates="connection")
    assets = relationship("PlatformAsset", back_populates="connection")
    listing_submissions = relationship("ListingSubmission", back_populates="connection")


class IntegrationSyncCursor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "integration_sync_cursors"
    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "resource_type",
            "cursor_name",
            name="uq_integration_sync_cursors_connection_resource_name",
        ),
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="CASCADE"), index=True
    )
    resource_type: Mapped[str] = mapped_column(String(64), index=True)
    cursor_name: Mapped[str] = mapped_column(String(64), default="default")
    cursor_value: Mapped[str | None] = mapped_column(Text)
    watermark_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_successful_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    extra_data: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )

    connection = relationship("IntegrationConnection", back_populates="sync_cursors")


class IntegrationRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "integration_runs"
    __table_args__ = (
        CheckConstraint("attempt_count > 0", name="attempt_count_positive"),
        CheckConstraint("records_read >= 0", name="records_read_nonnegative"),
        CheckConstraint("records_written >= 0", name="records_written_nonnegative"),
        CheckConstraint("records_failed >= 0", name="records_failed_nonnegative"),
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="RESTRICT"), index=True
    )
    correlation_id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    run_type: Mapped[str] = mapped_column(String(64), index=True)
    resource_type: Mapped[str] = mapped_column(String(64), index=True)
    direction: Mapped[IntegrationDirection] = mapped_column(
        string_enum(IntegrationDirection, "integration_direction")
    )
    status: Mapped[IntegrationRunStatus] = mapped_column(
        string_enum(IntegrationRunStatus, "integration_run_status"),
        default=IntegrationRunStatus.PENDING,
        server_default=IntegrationRunStatus.PENDING.value,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    records_read: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    records_written: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    records_failed: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    provider_request_id: Mapped[str | None] = mapped_column(String(255), index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )

    connection = relationship("IntegrationConnection", back_populates="runs")


class PlatformEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "platform_events"
    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "external_event_id",
            name="uq_platform_events_connection_external_event",
        ),
        CheckConstraint("attempt_count >= 0", name="attempt_count_nonnegative"),
    )

    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="RESTRICT"), index=True
    )
    external_event_id: Mapped[str] = mapped_column(String(255))
    event_type: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[IntegrationEventStatus] = mapped_column(
        string_enum(IntegrationEventStatus, "integration_event_status"),
        default=IntegrationEventStatus.RECEIVED,
        server_default=IntegrationEventStatus.RECEIVED.value,
        index=True,
    )
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )

    connection = relationship("IntegrationConnection", back_populates="events")

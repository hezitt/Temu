import uuid
from typing import Any

from sqlalchemy import JSON, Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import AuditStatus
from models.types import string_enum


class AuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"

    correlation_id: Mapped[uuid.UUID] = mapped_column(index=True)
    actor_type: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[str | None] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(128), index=True)
    entity_type: Mapped[str] = mapped_column(String(128), index=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    is_dry_run: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    status: Mapped[AuditStatus] = mapped_column(
        string_enum(AuditStatus, "audit_status"), index=True
    )
    before_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    after_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    error_message: Mapped[str | None] = mapped_column(Text)

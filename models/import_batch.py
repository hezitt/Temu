import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from models.enums import ImportStatus, ImportType
from models.types import string_enum


class ImportBatch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "import_batches"

    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("suppliers.id", ondelete="SET NULL"), index=True
    )
    import_type: Mapped[ImportType] = mapped_column(
        string_enum(ImportType, "import_type"), index=True
    )
    source_file_name: Mapped[str] = mapped_column(String(512))
    source_sha256: Mapped[str] = mapped_column(String(64), index=True)
    source_sheet: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[ImportStatus] = mapped_column(
        string_enum(ImportStatus, "import_status"),
        default=ImportStatus.PENDING,
        server_default=ImportStatus.PENDING.value,
        index=True,
    )
    row_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    success_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    warning_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    skipped_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_report_path: Mapped[str | None] = mapped_column(String(1024))
    correlation_id: Mapped[uuid.UUID] = mapped_column(index=True)
    extra_data: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=dict
    )

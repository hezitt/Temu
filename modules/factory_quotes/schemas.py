from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class VariantType(StrEnum):
    UNFRAMED = "UNFRAMED"
    FRAMED = "FRAMED"


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class RowStatus(StrEnum):
    VALID = "VALID"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"


class IssueCode(StrEnum):
    NO_QUOTE = "NO_QUOTE"
    SEPARATOR_ROW = "SEPARATOR_ROW"
    MISSING_COLOR_COUNT = "MISSING_COLOR_COUNT"
    INVALID_COLOR_COUNT = "INVALID_COLOR_COUNT"
    UNKNOWN_COLOR_COUNT = "UNKNOWN_COLOR_COUNT"
    INVALID_DIMENSION = "INVALID_DIMENSION"
    INVALID_COST = "INVALID_COST"
    NEGATIVE_COST = "NEGATIVE_COST"
    ZERO_COST = "ZERO_COST"
    SUSPICIOUSLY_LOW_COST = "SUSPICIOUSLY_LOW_COST"
    FRAMED_LOWER_THAN_UNFRAMED = "FRAMED_LOWER_THAN_UNFRAMED"
    COLOR_COST_INVERSION = "COLOR_COST_INVERSION"
    SIZE_COST_INVERSION = "SIZE_COST_INVERSION"
    DUPLICATE_QUOTE = "DUPLICATE_QUOTE"


class ImportMode(StrEnum):
    DRY_RUN = "DRY_RUN"
    COMMIT = "COMMIT"


class ValidationIssue(BaseModel):
    severity: Severity
    issue_code: IssueCode
    message: str


class RawQuoteCandidate(BaseModel):
    source_sheet: str
    source_row_number: int
    source_column: str
    variant_type: VariantType
    raw_color: Any = None
    raw_size: Any = None
    raw_cost: Any = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class NormalizedQuote(BaseModel):
    supplier_code: str
    product_type: str
    colors_count: int | None = None
    width_cm: Decimal | None = None
    height_cm: Decimal | None = None
    size_code: str | None = None
    variant_type: VariantType
    unit_cost: Decimal | None = None
    currency: str
    shipping_included: bool = False
    source_sheet: str
    source_row_number: int
    source_column: str
    raw_color: str | None = None
    raw_size: str | None = None
    raw_cost: str | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    issues: list[ValidationIssue] = Field(default_factory=list)

    def add_issue(self, issue: ValidationIssue) -> None:
        key = (issue.severity, issue.issue_code, issue.message)
        if key not in {(item.severity, item.issue_code, item.message) for item in self.issues}:
            self.issues.append(issue)

    @property
    def row_status(self) -> RowStatus:
        if any(issue.severity is Severity.ERROR for issue in self.issues):
            return RowStatus.ERROR
        if any(
            issue.issue_code in {IssueCode.NO_QUOTE, IssueCode.SEPARATOR_ROW}
            for issue in self.issues
        ):
            return RowStatus.SKIPPED
        if any(issue.severity is Severity.WARNING for issue in self.issues):
            return RowStatus.WARNING
        return RowStatus.VALID

    @property
    def is_importable(self) -> bool:
        return (
            self.row_status in {RowStatus.VALID, RowStatus.WARNING}
            and self.colors_count is not None
            and self.width_cm is not None
            and self.height_cm is not None
            and self.size_code is not None
            and self.unit_cost is not None
        )

    @property
    def business_key(self) -> tuple[str, int, Decimal, Decimal, VariantType] | None:
        if self.colors_count is None or self.width_cm is None or self.height_cm is None:
            return None
        return (
            self.product_type,
            self.colors_count,
            self.width_cm,
            self.height_cm,
            self.variant_type,
        )


class ImportPlan(BaseModel):
    insert_count: int = 0
    update_count: int = 0
    unchanged_count: int = 0


class ImportSummary(BaseModel):
    parsed_count: int
    valid_count: int
    warning_count: int
    error_count: int
    skipped_count: int
    issue_count: int


class ImportResult(BaseModel):
    batch_id: UUID
    mode: ImportMode
    supplier_code: str
    source_file: Path
    source_sha256: str
    source_sheet: str
    effective_date: date
    started_at: datetime
    completed_at: datetime | None = None
    summary: ImportSummary
    plan: ImportPlan = Field(default_factory=ImportPlan)
    records: list[NormalizedQuote]
    report_path: Path | None = None
    committed: bool = False

    @property
    def exit_code(self) -> int:
        return 2 if self.summary.error_count else 0


class DuplicateFileError(RuntimeError):
    pass


class SupplierNotConfiguredError(RuntimeError):
    pass

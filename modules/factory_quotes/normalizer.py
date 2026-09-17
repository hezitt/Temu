import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from modules.factory_quotes.schemas import (
    IssueCode,
    NormalizedQuote,
    RawQuoteCandidate,
    Severity,
    ValidationIssue,
)

COLOR_PATTERN = re.compile(r"^(\d+)\s*色?$")
SIZE_PATTERN = re.compile(
    r"^(\d+(?:\.\d+)?)\s*[xX×*]\s*(\d+(?:\.\d+)?)\s*(?:cm|厘米)?$",
    re.IGNORECASE,
)
MONEY_QUANTUM = Decimal("0.01")
DIMENSION_QUANTUM = Decimal("0.01")


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _decimal_label(value: Decimal) -> str:
    normalized = value.normalize()
    return format(normalized, "f")


def normalize_color(value: Any) -> int | None:
    text = _text(value)
    if text is None:
        return None
    match = COLOR_PATTERN.fullmatch(text)
    if match is None:
        raise ValueError(f"Invalid color count: {text}")
    return int(match.group(1))


def normalize_size(value: Any) -> tuple[Decimal, Decimal, str] | None:
    text = _text(value)
    if text is None:
        return None
    metric_part = text.split("/", maxsplit=1)[0].strip()
    match = SIZE_PATTERN.fullmatch(metric_part)
    if match is None:
        raise ValueError(f"Invalid size: {text}")
    width = Decimal(match.group(1)).quantize(DIMENSION_QUANTUM)
    height = Decimal(match.group(2)).quantize(DIMENSION_QUANTUM)
    if width <= 0 or height <= 0:
        raise ValueError(f"Invalid size: {text}")
    return width, height, f"{_decimal_label(width)}x{_decimal_label(height)}"


def normalize_cost(value: Any, unavailable_markers: set[str]) -> Decimal | None:
    text = _text(value)
    if text is None or text.upper() in unavailable_markers:
        return None
    if isinstance(value, bool):
        raise ValueError(f"Invalid cost: {text}")
    try:
        return Decimal(text.replace(",", "")).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid cost: {text}") from exc


class FactoryQuoteNormalizer:
    def __init__(
        self,
        supplier_code: str,
        currency: str,
        product_type: str,
        unavailable_markers: list[str],
    ) -> None:
        self.supplier_code = supplier_code.upper()
        self.currency = currency.upper()
        self.product_type = product_type
        self.unavailable_markers = {marker.strip().upper() for marker in unavailable_markers}

    def normalize(self, candidate: RawQuoteCandidate) -> NormalizedQuote:
        record = NormalizedQuote(
            supplier_code=self.supplier_code,
            product_type=self.product_type,
            variant_type=candidate.variant_type,
            currency=self.currency,
            shipping_included=False,
            source_sheet=candidate.source_sheet,
            source_row_number=candidate.source_row_number,
            source_column=candidate.source_column,
            raw_color=_text(candidate.raw_color),
            raw_size=_text(candidate.raw_size),
            raw_cost=_text(candidate.raw_cost),
            raw_payload=candidate.raw_payload,
        )

        if candidate.raw_payload.get("separator_hint"):
            record.add_issue(
                ValidationIssue(
                    severity=Severity.INFO,
                    issue_code=IssueCode.SEPARATOR_ROW,
                    message="分隔行中的 0 已跳过，不作为商品成本。",
                )
            )
            return record

        try:
            record.colors_count = normalize_color(candidate.raw_color)
        except ValueError:
            record.add_issue(
                ValidationIssue(
                    severity=Severity.ERROR,
                    issue_code=IssueCode.INVALID_COLOR_COUNT,
                    message=f"无法解析色数：{record.raw_color!r}。",
                )
            )

        try:
            normalized_size = normalize_size(candidate.raw_size)
            if normalized_size is not None:
                record.width_cm, record.height_cm, record.size_code = normalized_size
        except ValueError:
            record.add_issue(
                ValidationIssue(
                    severity=Severity.ERROR,
                    issue_code=IssueCode.INVALID_DIMENSION,
                    message=f"无法解析尺寸：{record.raw_size!r}。",
                )
            )

        try:
            record.unit_cost = normalize_cost(candidate.raw_cost, self.unavailable_markers)
        except ValueError:
            record.add_issue(
                ValidationIssue(
                    severity=Severity.ERROR,
                    issue_code=IssueCode.INVALID_COST,
                    message=f"无法解析报价：{record.raw_cost!r}。",
                )
            )

        return record

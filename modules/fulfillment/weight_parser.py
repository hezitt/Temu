import re
from decimal import Decimal
from typing import Any

from models.enums import VariantType
from modules.fulfillment.schemas import ProductWeightRuleRecord

COLOR_PATTERN = re.compile(r"(\d+)色")
SIZE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\*(\d+(?:\.\d+)?)cm", re.IGNORECASE)
WEIGHT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)g", re.IGNORECASE)


class WeightTableError(ValueError):
    pass


def parse_weight_rows(
    rows: list[list[Any]], *, source: str, source_hash: str
) -> list[ProductWeightRuleRecord]:
    records: list[ProductWeightRuleRecord] = []
    colors_count: int | None = None
    for row_number, row in enumerate(rows, start=1):
        padded = [*row, *([None] * max(0, 7 - len(row)))]
        color_match = COLOR_PATTERN.search(str(padded[0] or ""))
        if color_match:
            colors_count = int(color_match.group(1))
        if colors_count is None:
            continue
        for variant_type, size_index, package_index, weight_index in (
            (VariantType.UNFRAMED, 1, 2, 3),
            (VariantType.FRAMED, 4, 5, 6),
        ):
            size_text = str(padded[size_index] or "").strip()
            weight_text = str(padded[weight_index] or "").strip()
            if size_text in {"", "/"} and weight_text in {"", "/"}:
                continue
            size_match = SIZE_PATTERN.search(size_text)
            weight_match = WEIGHT_PATTERN.fullmatch(weight_text)
            if size_match is None or weight_match is None:
                raise WeightTableError(
                    f"Cannot parse weight rule at source row {row_number}: "
                    f"size={size_text!r}, weight={weight_text!r}"
                )
            records.append(
                ProductWeightRuleRecord(
                    width_cm=Decimal(size_match.group(1)),
                    height_cm=Decimal(size_match.group(2)),
                    colors_count=colors_count,
                    variant_type=variant_type,
                    weight=Decimal(weight_match.group(1)),
                    package_description=str(padded[package_index] or "").strip() or None,
                    source=source,
                    source_hash=source_hash,
                )
            )
    if not records:
        raise WeightTableError("No product weight rules found")
    return records

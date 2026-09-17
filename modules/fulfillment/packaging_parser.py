import re
from decimal import Decimal

from models.enums import VariantType
from modules.fulfillment.schemas import PackagingRuleRecord

DIMENSIONS_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\*(\d+(?:\.\d+)?)\*(\d+(?:\.\d+)?)\s*cm", re.IGNORECASE
)
SIZE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\*(\d+(?:\.\d+)?)")
COUNT_PATTERN = re.compile(r"(?:≤\s*)?(\d+)\s*件")


class PackagingTableError(ValueError):
    pass


def parse_packaging_tables(
    tables: list[list[list[str]]], *, source: str, source_hash: str
) -> list[PackagingRuleRecord]:
    if len(tables) < 2:
        raise PackagingTableError("Packaging document must contain unframed and framed tables")
    records: list[PackagingRuleRecord] = []
    records.extend(_parse_unframed(tables[0], source, source_hash))
    records.extend(_parse_framed(tables[1], source, source_hash))
    if not records:
        raise PackagingTableError("No packaging rules found")
    return records


def _parse_unframed(
    table: list[list[str]], source: str, source_hash: str
) -> list[PackagingRuleRecord]:
    records: list[PackagingRuleRecord] = []
    for row in table[1:]:
        if len(row) < 4:
            continue
        box = _parse_dimensions(row[0])
        sizes = _parse_sizes(row[1])
        notes = row[0].strip()
        for condition, count_text in (("<=24", row[2]), (">24", row[3])):
            count = _parse_count(count_text)
            if count is None:
                continue
            for width, height in sizes:
                records.append(
                    _record(
                        VariantType.UNFRAMED,
                        condition,
                        width,
                        height,
                        box,
                        count,
                        notes,
                        source,
                        source_hash,
                    )
                )
    return records


def _parse_framed(
    table: list[list[str]], source: str, source_hash: str
) -> list[PackagingRuleRecord]:
    records: list[PackagingRuleRecord] = []
    for row in table[1:]:
        if len(row) < 3:
            continue
        box = _parse_dimensions(row[0])
        sizes = _parse_sizes(row[1])
        count = _parse_count(row[2])
        if count is None:
            continue
        condition = "<=24" if "≤ 24" in row[2] or "≤24" in row[2] else "ANY"
        for width, height in sizes:
            records.append(
                _record(
                    VariantType.FRAMED,
                    condition,
                    width,
                    height,
                    box,
                    count,
                    row[0].strip(),
                    source,
                    source_hash,
                )
            )
    return records


def _parse_dimensions(text: str) -> tuple[Decimal, Decimal, Decimal]:
    match = DIMENSIONS_PATTERN.search(text)
    if match is None:
        raise PackagingTableError(f"Cannot parse box dimensions: {text!r}")
    return tuple(Decimal(value) for value in match.groups())  # type: ignore[return-value]


def _parse_sizes(text: str) -> list[tuple[Decimal, Decimal]]:
    return [(Decimal(width), Decimal(height)) for width, height in SIZE_PATTERN.findall(text)]


def _parse_count(text: str) -> int | None:
    match = COUNT_PATTERN.search(text)
    return int(match.group(1)) if match else None


def _record(
    variant_type: VariantType,
    condition: str,
    width: Decimal,
    height: Decimal,
    box: tuple[Decimal, Decimal, Decimal],
    count: int,
    notes: str,
    source: str,
    source_hash: str,
) -> PackagingRuleRecord:
    return PackagingRuleRecord(
        variant_type=variant_type,
        colors_count_condition=condition,
        width_cm=width,
        height_cm=height,
        box_length_cm=box[0],
        box_width_cm=box[1],
        box_height_cm=box[2],
        max_units_per_box=count,
        notes=notes,
        source=source,
        source_hash=source_hash,
    )

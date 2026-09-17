from decimal import Decimal

from modules.factory_quotes.anomaly_detector import FactoryQuoteAnomalyDetector
from modules.factory_quotes.schemas import IssueCode, NormalizedQuote, RowStatus, VariantType


def quote(
    *,
    colors: int = 24,
    width: str = "20",
    height: str = "20",
    variant: VariantType,
    cost: str,
    row: int,
) -> NormalizedQuote:
    return NormalizedQuote(
        supplier_code="LINGDIAN",
        product_type="PAINT_BY_NUMBERS",
        colors_count=colors,
        width_cm=Decimal(width),
        height_cm=Decimal(height),
        size_code=f"{width}x{height}",
        variant_type=variant,
        unit_cost=Decimal(cost),
        currency="CNY",
        source_sheet="Sheet1",
        source_row_number=row,
        source_column="E" if variant is VariantType.FRAMED else "C",
    )


def detector() -> FactoryQuoteAnomalyDetector:
    return FactoryQuoteAnomalyDetector(0.60, 0.90, 0.90)


def test_known_low_framed_cost_keeps_value_and_warns() -> None:
    unframed = quote(variant=VariantType.UNFRAMED, cost="25", row=4, colors=16)
    framed = quote(variant=VariantType.FRAMED, cost="9", row=4, colors=16)

    detector().detect([unframed, framed])

    assert framed.unit_cost == Decimal("9")
    assert framed.row_status is RowStatus.WARNING
    assert {issue.issue_code for issue in framed.issues} >= {
        IssueCode.FRAMED_LOWER_THAN_UNFRAMED,
        IssueCode.SUSPICIOUSLY_LOW_COST,
    }


def test_duplicate_quote_is_error() -> None:
    first = quote(variant=VariantType.UNFRAMED, cost="44", row=10)
    second = quote(variant=VariantType.UNFRAMED, cost="44", row=11)

    detector().detect([first, second])

    assert first.row_status is RowStatus.ERROR
    assert second.row_status is RowStatus.ERROR
    assert all(
        any(issue.issue_code is IssueCode.DUPLICATE_QUOTE for issue in record.issues)
        for record in [first, second]
    )


def test_color_and_size_inversions_are_warnings() -> None:
    fewer_colors = quote(variant=VariantType.UNFRAMED, cost="100", row=1, colors=24)
    more_colors = quote(variant=VariantType.UNFRAMED, cost="80", row=2, colors=36)
    smaller = quote(
        variant=VariantType.FRAMED, cost="100", row=3, colors=24, width="20", height="20"
    )
    larger = quote(variant=VariantType.FRAMED, cost="80", row=4, colors=24, width="40", height="50")

    detector().detect([fewer_colors, more_colors, smaller, larger])

    assert any(issue.issue_code is IssueCode.COLOR_COST_INVERSION for issue in more_colors.issues)
    assert any(issue.issue_code is IssueCode.SIZE_COST_INVERSION for issue in larger.issues)

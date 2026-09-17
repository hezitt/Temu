from decimal import Decimal

from modules.factory_quotes.schemas import IssueCode, NormalizedQuote, RowStatus, VariantType
from modules.factory_quotes.validator import FactoryQuoteValidator


def quote(cost: Decimal | None, colors: int = 24) -> NormalizedQuote:
    return NormalizedQuote(
        supplier_code="LINGDIAN",
        product_type="PAINT_BY_NUMBERS",
        colors_count=colors,
        width_cm=Decimal("40"),
        height_cm=Decimal("50"),
        size_code="40x50",
        variant_type=VariantType.UNFRAMED,
        unit_cost=cost,
        currency="CNY",
        source_sheet="Sheet1",
        source_row_number=10,
        source_column="C",
    )


def test_zero_is_error() -> None:
    record = FactoryQuoteValidator({16, 24, 36, 48, 60}).validate(quote(Decimal("0")))
    assert record.row_status is RowStatus.ERROR
    assert any(issue.issue_code is IssueCode.ZERO_COST for issue in record.issues)


def test_negative_is_error() -> None:
    record = FactoryQuoteValidator({16, 24, 36, 48, 60}).validate(quote(Decimal("-1")))
    assert record.row_status is RowStatus.ERROR
    assert any(issue.issue_code is IssueCode.NEGATIVE_COST for issue in record.issues)


def test_null_cost_is_skipped_not_zero() -> None:
    record = FactoryQuoteValidator({16, 24, 36, 48, 60}).validate(quote(None))
    assert record.unit_cost is None
    assert record.row_status is RowStatus.SKIPPED
    assert any(issue.issue_code is IssueCode.NO_QUOTE for issue in record.issues)


def test_unknown_color_is_warning() -> None:
    record = FactoryQuoteValidator({16, 24, 36, 48, 60}).validate(quote(Decimal("44"), 72))
    assert record.row_status is RowStatus.WARNING
    assert any(issue.issue_code is IssueCode.UNKNOWN_COLOR_COUNT for issue in record.issues)

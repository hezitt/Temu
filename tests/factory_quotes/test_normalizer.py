from decimal import Decimal

import pytest

from modules.factory_quotes.normalizer import normalize_color, normalize_cost, normalize_size


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("40×50 cm", (Decimal("40.00"), Decimal("50.00"), "40x50")),
        ("40x50", (Decimal("40.00"), Decimal("50.00"), "40x50")),
        ("40 X 50", (Decimal("40.00"), Decimal("50.00"), "40x50")),
        ("40*50cm/16*20inch", (Decimal("40.00"), Decimal("50.00"), "40x50")),
    ],
)
def test_size_normalization(raw: str, expected: tuple[Decimal, Decimal, str]) -> None:
    assert normalize_size(raw) == expected


@pytest.mark.parametrize("raw", ["40×", "abc", "0x50", "-40x50"])
def test_invalid_size(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_size(raw)


@pytest.mark.parametrize(("raw", "expected"), [("16色", 16), ("24色", 24), ("60", 60)])
def test_color_normalization(raw: str, expected: int) -> None:
    assert normalize_color(raw) == expected


def test_invalid_color() -> None:
    with pytest.raises(ValueError):
        normalize_color("很多色")


@pytest.mark.parametrize("raw", [None, "", "/", "NULL", "N/A", "-"])
def test_no_quote_cost(raw: object) -> None:
    assert normalize_cost(raw, {"/", "NULL", "N/A", "-"}) is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(44, Decimal("44.00")), ("44.1", Decimal("44.10")), (44.125, Decimal("44.13"))],
)
def test_decimal_cost(raw: object, expected: Decimal) -> None:
    assert normalize_cost(raw, {"/"}) == expected


def test_invalid_cost_string() -> None:
    with pytest.raises(ValueError):
        normalize_cost("not-a-price", {"/"})

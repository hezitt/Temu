from decimal import Decimal

import pytest

from models.enums import VariantType
from modules.fulfillment.profile_resolver import (
    FulfillmentProfileError,
    FulfillmentProfileResolver,
)
from modules.fulfillment.schemas import PackagingRuleRecord, ProductWeightRuleRecord


def packaging_rule(condition: str = "<=24") -> PackagingRuleRecord:
    return PackagingRuleRecord(
        variant_type=VariantType.UNFRAMED,
        colors_count_condition=condition,
        width_cm=Decimal("40"),
        height_cm=Decimal("50"),
        box_length_cm=Decimal("55"),
        box_width_cm=Decimal("8"),
        box_height_cm=Decimal("5.5"),
        max_units_per_box=2,
        source="packing.docx",
        source_hash="a" * 64,
    )


def weight_rule() -> ProductWeightRuleRecord:
    return ProductWeightRuleRecord(
        variant_type=VariantType.UNFRAMED,
        width_cm=Decimal("40"),
        height_cm=Decimal("50"),
        colors_count=24,
        weight=Decimal("399"),
        source="weight.xls",
        source_hash="b" * 64,
    )


def test_resolver_combines_packaging_and_weight_with_provenance() -> None:
    result = FulfillmentProfileResolver().resolve(
        [packaging_rule()],
        [weight_rule()],
        width_cm=Decimal("40"),
        height_cm=Decimal("50"),
        colors_count=24,
        framed=False,
    )

    assert result is not None
    assert (result.box_length_cm, result.box_width_cm, result.box_height_cm) == (
        Decimal("55"),
        Decimal("8"),
        Decimal("5.5"),
    )
    assert result.weight_g == Decimal("399")
    assert result.max_units_per_box == 2
    assert result.packaging_source_hash == "a" * 64
    assert result.weight_source_hash == "b" * 64


def test_resolver_does_not_guess_when_only_one_rule_type_matches() -> None:
    with pytest.raises(FulfillmentProfileError, match="weight rule"):
        FulfillmentProfileResolver().resolve(
            [packaging_rule()],
            [],
            width_cm=Decimal("40"),
            height_cm=Decimal("50"),
            colors_count=24,
            framed=False,
        )

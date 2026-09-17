from dataclasses import dataclass
from decimal import Decimal

from models.enums import VariantType
from modules.fulfillment.schemas import PackagingRuleRecord, ProductWeightRuleRecord


class FulfillmentProfileError(ValueError):
    pass


@dataclass(frozen=True)
class FulfillmentProfile:
    box_length_cm: Decimal
    box_width_cm: Decimal
    box_height_cm: Decimal
    weight_g: Decimal
    max_units_per_box: int
    packaging_source: str
    packaging_source_hash: str
    weight_source: str
    weight_source_hash: str


class FulfillmentProfileResolver:
    def resolve(
        self,
        packaging_rules: list[PackagingRuleRecord],
        weight_rules: list[ProductWeightRuleRecord],
        *,
        width_cm: Decimal,
        height_cm: Decimal,
        colors_count: int,
        framed: bool,
    ) -> FulfillmentProfile | None:
        variant_type = VariantType.FRAMED if framed else VariantType.UNFRAMED
        packaging_matches = [
            rule
            for rule in packaging_rules
            if rule.variant_type is variant_type
            and rule.width_cm == width_cm
            and rule.height_cm == height_cm
            and _matches_color_condition(rule.colors_count_condition, colors_count)
        ]
        weight_matches = [
            rule
            for rule in weight_rules
            if rule.variant_type is variant_type
            and rule.width_cm == width_cm
            and rule.height_cm == height_cm
            and rule.colors_count == colors_count
        ]
        if not packaging_matches and not weight_matches:
            return None
        if len(packaging_matches) != 1:
            raise FulfillmentProfileError(
                "Expected exactly one packaging rule for "
                f"{variant_type.value} {width_cm}x{height_cm} {colors_count} colors; "
                f"found {len(packaging_matches)}"
            )
        if len(weight_matches) != 1:
            raise FulfillmentProfileError(
                "Expected exactly one weight rule for "
                f"{variant_type.value} {width_cm}x{height_cm} {colors_count} colors; "
                f"found {len(weight_matches)}"
            )
        packaging = packaging_matches[0]
        weight = weight_matches[0]
        if weight.weight_unit.lower() != "g":
            raise FulfillmentProfileError(
                f"Unsupported weight unit {weight.weight_unit!r}; no conversion was guessed"
            )
        return FulfillmentProfile(
            box_length_cm=packaging.box_length_cm,
            box_width_cm=packaging.box_width_cm,
            box_height_cm=packaging.box_height_cm,
            weight_g=weight.weight,
            max_units_per_box=packaging.max_units_per_box,
            packaging_source=packaging.source,
            packaging_source_hash=packaging.source_hash,
            weight_source=weight.source,
            weight_source_hash=weight.source_hash,
        )


def _matches_color_condition(condition: str, colors_count: int) -> bool:
    normalized = condition.replace(" ", "").upper()
    if normalized == "ANY":
        return True
    if normalized == "<=24":
        return colors_count <= 24
    if normalized == ">24":
        return colors_count > 24
    raise FulfillmentProfileError(f"Unsupported packaging color condition: {condition!r}")

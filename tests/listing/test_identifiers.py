from decimal import Decimal

import pytest

from integrations.fangguo.naming import (
    InvalidFactoryDesignCodeError,
    build_material_names,
    validate_material_pair,
)
from modules.listing.sku_generator import InvalidSKUComponentError, generate_sku


def test_factory_material_names_follow_fangguo_pairing_rule() -> None:
    names = build_material_names("CAT000001")
    assert names.line_art == "CAT000001.jpg"
    assert names.instruction == "CAT000001@说明书.jpg"
    validate_material_pair("CAT000001", names.line_art, names.instruction)


def test_factory_design_code_rejects_internal_hyphenated_design_id() -> None:
    with pytest.raises(InvalidFactoryDesignCodeError):
        build_material_names("DESIGN-CAT-000001")


def test_sku_generation_is_deterministic_and_encodes_variant() -> None:
    first = generate_sku("CAT000001", Decimal("40"), Decimal("50"), 24, False)
    second = generate_sku("CAT000001", Decimal("40.00"), Decimal("50.0"), 24, False)
    assert first == second == "PBN-CAT000001-4050-24-U"
    assert generate_sku("CAT000001", Decimal("30"), Decimal("40"), 24, True).endswith("-3040-24-F")


def test_sku_generation_rejects_fractional_dimensions_in_v1() -> None:
    with pytest.raises(InvalidSKUComponentError):
        generate_sku("CAT000001", Decimal("40.5"), Decimal("50"), 24, False)

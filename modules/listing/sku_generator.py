from decimal import Decimal


class InvalidSKUComponentError(ValueError):
    pass


def _whole_centimeters(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized != normalized.to_integral_value():
        raise InvalidSKUComponentError("V1 SKU dimensions must be whole centimeters")
    integer = int(normalized)
    if integer <= 0 or integer > 999:
        raise InvalidSKUComponentError("SKU dimensions must be between 1 and 999 cm")
    return str(integer)


def build_size_code(width_cm: Decimal, height_cm: Decimal) -> str:
    return f"{_whole_centimeters(width_cm)}{_whole_centimeters(height_cm)}"


def generate_sku(
    factory_design_code: str,
    width_cm: Decimal,
    height_cm: Decimal,
    colors_count: int,
    framed: bool,
) -> str:
    if colors_count <= 0:
        raise InvalidSKUComponentError("colors_count must be positive")
    frame_code = "F" if framed else "U"
    size_code = build_size_code(width_cm, height_cm)
    return f"PBN-{factory_design_code}-{size_code}-{colors_count}-{frame_code}"


def generate_spu_item_code(factory_design_code: str) -> str:
    return f"PBN-{factory_design_code}"

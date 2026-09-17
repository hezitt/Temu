import re
from dataclasses import dataclass

FACTORY_DESIGN_CODE_PATTERN = re.compile(r"^[A-Z0-9_]+$")


class InvalidFactoryDesignCodeError(ValueError):
    pass


@dataclass(frozen=True)
class FactoryMaterialNames:
    line_art: str
    instruction: str


def validate_factory_design_code(factory_design_code: str) -> str:
    code = factory_design_code.strip()
    if not FACTORY_DESIGN_CODE_PATTERN.fullmatch(code):
        raise InvalidFactoryDesignCodeError(
            "Factory Design Code may contain only uppercase ASCII letters, digits, and underscores"
        )
    return code


def build_material_names(factory_design_code: str, extension: str = ".jpg") -> FactoryMaterialNames:
    code = validate_factory_design_code(factory_design_code)
    normalized_extension = extension.lower()
    if normalized_extension not in {".jpg", ".jpeg", ".png"}:
        raise InvalidFactoryDesignCodeError("Factory material image must be JPG, JPEG, or PNG")
    return FactoryMaterialNames(
        line_art=f"{code}{normalized_extension}",
        instruction=f"{code}@说明书{normalized_extension}",
    )


def validate_material_pair(
    factory_design_code: str, line_art_filename: str, instruction_filename: str
) -> None:
    extension = "." + line_art_filename.rsplit(".", 1)[-1]
    expected = build_material_names(factory_design_code, extension)
    if line_art_filename != expected.line_art or instruction_filename != expected.instruction:
        raise InvalidFactoryDesignCodeError(
            f"Material pair must be {expected.line_art!r} and {expected.instruction!r}"
        )

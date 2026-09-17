from sqlalchemy import Enum as SAEnum

from models.enums import StringEnum


def string_enum(enum_class: type[StringEnum], name: str) -> SAEnum:
    return SAEnum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
    )

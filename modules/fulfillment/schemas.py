from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from models.enums import VariantType


class PackagingRuleRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    variant_type: VariantType
    colors_count_condition: str
    width_cm: Decimal = Field(gt=0)
    height_cm: Decimal = Field(gt=0)
    box_length_cm: Decimal = Field(gt=0)
    box_width_cm: Decimal = Field(gt=0)
    box_height_cm: Decimal = Field(gt=0)
    max_units_per_box: int = Field(gt=0)
    notes: str | None = None
    source: str
    source_hash: str


class ProductWeightRuleRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    width_cm: Decimal = Field(gt=0)
    height_cm: Decimal = Field(gt=0)
    colors_count: int = Field(gt=0)
    variant_type: VariantType
    weight: Decimal = Field(gt=0)
    weight_unit: str = "g"
    package_description: str | None = None
    source: str
    source_hash: str

from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from modules.costing.schemas import FactoryCostMatch, ShippingCostEstimate, UnitCostBreakdown


class VariantInput(BaseModel):
    width_cm: Decimal = Field(gt=0)
    height_cm: Decimal = Field(gt=0)
    colors_count: int = Field(gt=0)
    framed: bool
    override_no_quote: bool = False


class DesignInput(BaseModel):
    design_id: str = Field(min_length=1)
    factory_design_code: str = Field(min_length=1)
    title_base: str = Field(min_length=1)
    theme: str = Field(min_length=1)
    main_image: Path
    additional_images: list[Path] = Field(default_factory=list)
    available_variants: list[VariantInput] = Field(min_length=1)
    product_type: str = "PAINT_BY_NUMBERS"
    target_market: str = "US"

    @field_validator("design_id", "factory_design_code", "title_base", "theme")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class DesignBatchInput(BaseModel):
    designs: list[DesignInput] = Field(min_length=1)


class ListingIssue(BaseModel):
    model_config = ConfigDict(frozen=True)

    severity: Literal["ERROR", "WARNING"]
    code: str
    message: str
    design_id: str
    sku: str | None = None


class ListingSKU(BaseModel):
    factory_sku: str
    width_cm: Decimal
    height_cm: Decimal
    colors_count: int
    framed: bool
    factory_cost: FactoryCostMatch | None
    shipping_cost: ShippingCostEstimate | None
    unit_cost: UnitCostBreakdown | None
    valid: bool = True


class ListingProduct(BaseModel):
    design_id: str
    factory_design_code: str
    title: str
    theme: str
    main_image: Path
    additional_images: list[Path]
    product_type: str
    target_market: str
    skus: list[ListingSKU]
    issues: list[ListingIssue] = Field(default_factory=list)
    valid: bool = True


class ListingBatch(BaseModel):
    products: list[ListingProduct]
    issues: list[ListingIssue] = Field(default_factory=list)


class CanonicalListingRow(BaseModel):
    design_id: str
    factory_design_code: str
    title: str
    theme: str
    product_type: str
    target_market: str
    main_image: str
    additional_images: str
    sku: str
    width_cm: Decimal
    height_cm: Decimal
    colors_count: int
    framed: bool
    factory_cost_cny: Decimal
    shipping_cost_usd: Decimal
    unit_variable_cost_cny: Decimal

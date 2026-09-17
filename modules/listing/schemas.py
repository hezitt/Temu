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
    sku_image_ref: str | None = None
    declared_price_cny: Decimal | None = Field(default=None, gt=0)
    warehouse_inventory: int | None = Field(default=None, ge=0)
    package_length_cm: Decimal | None = Field(default=None, gt=0)
    package_width_cm: Decimal | None = Field(default=None, gt=0)
    package_height_cm: Decimal | None = Field(default=None, gt=0)
    package_weight_g: Decimal | None = Field(default=None, ge=2)


class DesignInput(BaseModel):
    design_id: str = Field(min_length=1)
    factory_design_code: str = Field(min_length=1)
    title_base: str = Field(min_length=1)
    title_zh: str | None = None
    theme: str = Field(min_length=1)
    main_image: Path
    additional_images: list[Path] = Field(default_factory=list)
    publish_image_refs: list[str] = Field(default_factory=list)
    style_tags: list[str] = Field(default_factory=list, max_length=3)
    theme_tags: list[str] = Field(default_factory=list, max_length=3)
    sensitive_attributes: list[str] = Field(default_factory=list, max_length=7)
    origin_country: str = "中国大陆"
    origin_province: str | None = "河南省"
    manufacturing_regions: list[str] = Field(default_factory=lambda: ["中国大陆"], max_length=10)
    material: str = "油画布"
    asset_rights_confirmed: bool = False
    compliance_manifest: Path | None = None
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
    sku_image_ref: str | None = None
    declared_price_cny: Decimal | None = None
    warehouse_inventory: int | None = None
    package_length_cm: Decimal | None = None
    package_width_cm: Decimal | None = None
    package_height_cm: Decimal | None = None
    package_weight_g: Decimal | None = None
    max_units_per_box: int | None = None
    packaging_source: str | None = None
    packaging_source_hash: str | None = None
    weight_source: str | None = None
    weight_source_hash: str | None = None
    factory_cost: FactoryCostMatch | None
    shipping_cost: ShippingCostEstimate | None
    unit_cost: UnitCostBreakdown | None
    valid: bool = True


class ListingProduct(BaseModel):
    design_id: str
    factory_design_code: str
    title: str
    title_zh: str | None = None
    theme: str
    main_image: Path
    additional_images: list[Path]
    publish_image_refs: list[str] = Field(default_factory=list)
    style_tags: list[str] = Field(default_factory=list)
    theme_tags: list[str] = Field(default_factory=list)
    sensitive_attributes: list[str] = Field(default_factory=list)
    origin_country: str = "中国大陆"
    origin_province: str | None = "河南省"
    manufacturing_regions: list[str] = Field(default_factory=list)
    material: str = "油画布"
    asset_rights_confirmed: bool = False
    compliance_manifest: Path | None = None
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
    spu_item_code: str
    title: str
    title_zh: str | None = None
    theme: str
    product_type: str
    target_market: str
    main_image: str
    additional_images: str
    publish_image_refs: list[str] = Field(default_factory=list)
    style_tags: list[str] = Field(default_factory=list)
    theme_tags: list[str] = Field(default_factory=list)
    sensitive_attributes: list[str] = Field(default_factory=list)
    origin_country: str
    origin_province: str | None = None
    manufacturing_regions: list[str] = Field(default_factory=list)
    material: str
    sku: str
    width_cm: Decimal
    height_cm: Decimal
    colors_count: int
    framed: bool
    sku_image_ref: str | None = None
    declared_price_cny: Decimal | None = None
    warehouse_inventory: int | None = None
    package_length_cm: Decimal | None = None
    package_width_cm: Decimal | None = None
    package_height_cm: Decimal | None = None
    package_weight_g: Decimal | None = None
    max_units_per_box: int | None = None
    packaging_source: str | None = None
    packaging_source_hash: str | None = None
    weight_source: str | None = None
    weight_source_hash: str | None = None
    factory_cost_cny: Decimal
    shipping_cost_usd: Decimal
    unit_variable_cost_cny: Decimal

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from models.enums import ExchangeRateSource, LabelServiceCostStatus, ShippingCostType


class MissingExchangeRateError(ValueError):
    pass


class FactoryCostMatch(BaseModel):
    model_config = ConfigDict(frozen=True)

    factory_cost_id: uuid.UUID | None = None
    supplier_code: str
    factory_cost_cny: Decimal = Field(ge=0)
    currency: Literal["CNY"] = "CNY"
    colors_count: int = Field(gt=0)
    width_cm: Decimal = Field(gt=0)
    height_cm: Decimal = Field(gt=0)
    framed: bool
    source_sheet: str | None = None
    source_row: int | None = None

    @property
    def source_description(self) -> str:
        parts = [self.supplier_code]
        if self.source_sheet:
            parts.append(self.source_sheet)
        if self.source_row is not None:
            parts.append(f"row {self.source_row}")
        return " / ".join(parts)


class ShippingCostEstimate(BaseModel):
    model_config = ConfigDict(frozen=True)

    amount_usd: Decimal = Field(ge=0)
    cost_type: ShippingCostType
    source: str


class ExchangeRateSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    usd_cny_rate: Decimal = Field(gt=0)
    source: ExchangeRateSource = ExchangeRateSource.MANUAL_CONFIG
    timestamp: datetime


class LabelServiceCost(BaseModel):
    model_config = ConfigDict(frozen=True)

    amount_cny: Decimal = Field(ge=0)
    status: LabelServiceCostStatus


class DesignCostSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    line_art_cost: Decimal | None
    currency: str | None
    paid: bool
    paid_at: datetime | None
    reusable: bool
    allocation_policy: Literal["ONE_TIME_DESIGN_COST"] = "ONE_TIME_DESIGN_COST"


class UnitCostBreakdown(BaseModel):
    model_config = ConfigDict(frozen=True)

    factory_cost_id: uuid.UUID | None
    factory_cost_cny: Decimal
    factory_cost_source: str
    shipping_cost_usd: Decimal
    exchange_rate: Decimal
    exchange_rate_source: ExchangeRateSource
    exchange_rate_timestamp: datetime
    shipping_cost_cny: Decimal
    unit_variable_cost_cny: Decimal
    shipping_cost_type: ShippingCostType
    label_service_cost_cny: Decimal
    label_service_cost_status: LabelServiceCostStatus
    cost_completeness_status: Literal["ESTIMATED"] = "ESTIMATED"

    @field_serializer(
        "factory_cost_cny",
        "shipping_cost_usd",
        "exchange_rate",
        "shipping_cost_cny",
        "unit_variable_cost_cny",
        "label_service_cost_cny",
    )
    def serialize_decimal(self, value: Decimal) -> str:
        return format(value, "f")

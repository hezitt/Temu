from decimal import ROUND_HALF_UP, Decimal

from core.config import CostingSettings
from models.enums import ExchangeRateSource, LabelServiceCostStatus
from modules.costing.schemas import (
    ExchangeRateSnapshot,
    FactoryCostMatch,
    LabelServiceCost,
    MissingExchangeRateError,
    ShippingCostEstimate,
    UnitCostBreakdown,
)

CENT = Decimal("0.01")


class UnitCostService:
    def __init__(self, settings: CostingSettings) -> None:
        self.settings = settings

    def configured_exchange_rate(self) -> ExchangeRateSnapshot:
        rate = self.settings.usd_cny_exchange_rate
        timestamp = self.settings.exchange_rate_timestamp
        if rate is None or timestamp is None:
            raise MissingExchangeRateError(
                "Configure COSTING__USD_CNY_EXCHANGE_RATE and "
                "COSTING__EXCHANGE_RATE_TIMESTAMP before calculating a complete unit cost."
            )
        if self.settings.exchange_rate_source != ExchangeRateSource.MANUAL_CONFIG.value:
            raise MissingExchangeRateError("V1 only supports MANUAL_CONFIG exchange rates")
        return ExchangeRateSnapshot(
            usd_cny_rate=rate,
            source=ExchangeRateSource.MANUAL_CONFIG,
            timestamp=timestamp,
        )

    def label_service_cost(self) -> LabelServiceCost:
        return LabelServiceCost(
            amount_cny=self.settings.label_service_cost_cny,
            status=LabelServiceCostStatus(self.settings.label_service_cost_status),
        )

    def calculate(
        self,
        *,
        factory_cost: FactoryCostMatch,
        shipping_cost: ShippingCostEstimate,
        exchange_rate: ExchangeRateSnapshot | None = None,
    ) -> UnitCostBreakdown:
        rate = exchange_rate or self.configured_exchange_rate()
        label = self.label_service_cost()
        shipping_cny = (shipping_cost.amount_usd * rate.usd_cny_rate).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
        unit_cost = (factory_cost.factory_cost_cny + shipping_cny).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
        return UnitCostBreakdown(
            factory_cost_id=factory_cost.factory_cost_id,
            factory_cost_cny=factory_cost.factory_cost_cny.quantize(CENT),
            factory_cost_source=factory_cost.source_description,
            shipping_cost_usd=shipping_cost.amount_usd.quantize(CENT),
            exchange_rate=rate.usd_cny_rate,
            exchange_rate_source=rate.source,
            exchange_rate_timestamp=rate.timestamp,
            shipping_cost_cny=shipping_cny,
            unit_variable_cost_cny=unit_cost,
            shipping_cost_type=shipping_cost.cost_type,
            label_service_cost_cny=label.amount_cny.quantize(CENT),
            label_service_cost_status=label.status,
        )

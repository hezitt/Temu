from core.config import CostingSettings
from models.enums import ShippingCostType
from modules.costing.schemas import ShippingCostEstimate


class ShippingCostResolver:
    def __init__(self, settings: CostingSettings) -> None:
        self.settings = settings

    def resolve_estimate(self) -> ShippingCostEstimate:
        return ShippingCostEstimate(
            amount_usd=self.settings.estimated_shipping_cost_usd,
            cost_type=ShippingCostType.ESTIMATED_AVERAGE,
            source="costing.estimated_shipping_cost_usd",
        )

from models import Design
from modules.costing.schemas import DesignCostSnapshot


class DesignCostService:
    @staticmethod
    def snapshot(design: Design) -> DesignCostSnapshot:
        return DesignCostSnapshot(
            line_art_cost=design.line_art_cost,
            currency=design.line_art_cost_currency,
            paid=design.line_art_cost_paid,
            paid_at=design.line_art_cost_paid_at,
            reusable=design.line_art_reusable,
        )

from collections.abc import Iterable
from datetime import date
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import FactoryCost, Supplier
from models.enums import ValidationStatus
from modules.costing.schemas import FactoryCostMatch


class FactoryCostResolver:
    @staticmethod
    def resolve_from_catalog(
        catalog: Iterable[FactoryCostMatch],
        *,
        supplier_code: str,
        colors_count: int,
        width_cm: Decimal,
        height_cm: Decimal,
        framed: bool,
    ) -> FactoryCostMatch | None:
        target = (colors_count, width_cm, height_cm, framed)
        for match in catalog:
            if match.supplier_code.upper() != supplier_code.upper():
                continue
            if (match.colors_count, match.width_cm, match.height_cm, match.framed) == target:
                return match
        return None

    async def resolve(
        self,
        session: AsyncSession,
        *,
        supplier_code: str,
        colors_count: int,
        width_cm: Decimal,
        height_cm: Decimal,
        framed: bool,
        effective_on: date | None = None,
    ) -> FactoryCostMatch | None:
        on_date = effective_on or date.today()
        statement = (
            select(FactoryCost, Supplier.supplier_code)
            .join(Supplier, FactoryCost.supplier_id == Supplier.id)
            .where(
                Supplier.supplier_code == supplier_code.upper(),
                FactoryCost.colors_count == colors_count,
                FactoryCost.width_cm == width_cm,
                FactoryCost.height_cm == height_cm,
                FactoryCost.framed.is_(framed),
                FactoryCost.effective_from <= on_date,
                or_(FactoryCost.effective_to.is_(None), FactoryCost.effective_to >= on_date),
                FactoryCost.validation_status != ValidationStatus.INVALID,
                FactoryCost.currency == "CNY",
            )
            .order_by(FactoryCost.effective_from.desc())
            .limit(1)
        )
        row = (await session.execute(statement)).one_or_none()
        if row is None:
            return None
        cost, code = row
        return FactoryCostMatch(
            factory_cost_id=cost.id,
            supplier_code=code,
            factory_cost_cny=cost.base_product_cost,
            colors_count=cost.colors_count,
            width_cm=cost.width_cm,
            height_cm=cost.height_cm,
            framed=cost.framed,
            source_sheet=cost.source_sheet,
            source_row=cost.source_row,
        )

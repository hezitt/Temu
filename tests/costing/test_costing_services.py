from datetime import UTC, datetime
from decimal import Decimal

import pytest

from core.config import CostingSettings
from models import Design
from models.enums import LabelServiceCostStatus, ShippingCostType
from modules.costing.design_cost_service import DesignCostService
from modules.costing.factory_cost_resolver import FactoryCostResolver
from modules.costing.schemas import FactoryCostMatch, MissingExchangeRateError
from modules.costing.shipping_cost_resolver import ShippingCostResolver
from modules.costing.unit_cost_service import UnitCostService


def configured_costing() -> CostingSettings:
    return CostingSettings(
        estimated_shipping_cost_usd=Decimal("4.00"),
        usd_cny_exchange_rate=Decimal("7.25"),
        exchange_rate_timestamp=datetime(2026, 9, 17, tzinfo=UTC),
    )


def factory_match() -> FactoryCostMatch:
    return FactoryCostMatch(
        supplier_code="LINGDIAN",
        factory_cost_cny=Decimal("44.00"),
        colors_count=24,
        width_cm=Decimal("40"),
        height_cm=Decimal("50"),
        framed=False,
        source_sheet="Sheet1",
        source_row=10,
    )


def test_shipping_estimate_comes_from_decimal_configuration() -> None:
    shipping = ShippingCostResolver(configured_costing()).resolve_estimate()
    assert shipping.amount_usd == Decimal("4.00")
    assert shipping.cost_type is ShippingCostType.ESTIMATED_AVERAGE


def test_unit_cost_uses_factory_plus_shipping_and_confirmed_zero_label() -> None:
    settings = configured_costing()
    result = UnitCostService(settings).calculate(
        factory_cost=factory_match(),
        shipping_cost=ShippingCostResolver(settings).resolve_estimate(),
    )
    assert result.shipping_cost_cny == Decimal("29.00")
    assert result.unit_variable_cost_cny == Decimal("73.00")
    assert result.label_service_cost_cny == Decimal("0.00")
    assert result.label_service_cost_status is LabelServiceCostStatus.CONFIRMED
    assert result.factory_cost_source == "LINGDIAN / Sheet1 / row 10"


def test_missing_manual_exchange_rate_blocks_complete_unit_cost() -> None:
    settings = CostingSettings()
    with pytest.raises(MissingExchangeRateError):
        UnitCostService(settings).calculate(
            factory_cost=factory_match(),
            shipping_cost=ShippingCostResolver(settings).resolve_estimate(),
        )


def test_line_art_cost_is_a_separate_one_time_design_cost() -> None:
    design = Design(
        design_code="DESIGN-CAT-000001",
        factory_design_code="CAT000001",
        line_art_cost=Decimal("120.00"),
        line_art_cost_currency="CNY",
        line_art_cost_paid=False,
        line_art_reusable=True,
    )
    snapshot = DesignCostService.snapshot(design)
    result = UnitCostService(configured_costing()).calculate(
        factory_cost=factory_match(),
        shipping_cost=ShippingCostResolver(configured_costing()).resolve_estimate(),
    )
    assert snapshot.line_art_cost == Decimal("120.00")
    assert snapshot.allocation_policy == "ONE_TIME_DESIGN_COST"
    assert result.unit_variable_cost_cny == Decimal("73.00")


def test_factory_cost_resolver_returns_none_for_no_quote() -> None:
    match = FactoryCostResolver.resolve_from_catalog(
        [factory_match()],
        supplier_code="LINGDIAN",
        colors_count=60,
        width_cm=Decimal("20"),
        height_cm=Decimal("20"),
        framed=True,
    )
    assert match is None

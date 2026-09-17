from decimal import Decimal

import pytest
from pydantic import ValidationError

from core.config import PricingSettings, Settings


def test_default_margin_configuration() -> None:
    settings = Settings(_env_file=None)
    assert settings.pricing.min_margin == 0.30
    assert settings.pricing.target_margin == 0.35
    assert settings.pricing.require_dry_run is True


def test_margin_order_is_validated() -> None:
    with pytest.raises(ValidationError):
        PricingSettings(min_margin=0.35, target_margin=0.35)


def test_costing_defaults_keep_zero_distinct_from_missing_exchange_rate() -> None:
    settings = Settings(_env_file=None)
    assert settings.costing.estimated_shipping_cost_usd == Decimal("4.00")
    assert settings.costing.label_service_cost_cny == Decimal("0.00")
    assert settings.costing.usd_cny_exchange_rate is None

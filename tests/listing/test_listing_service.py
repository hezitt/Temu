from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from core.config import CostingSettings, ListingSettings
from modules.costing.factory_cost_resolver import FactoryCostResolver
from modules.costing.schemas import FactoryCostMatch
from modules.costing.shipping_cost_resolver import ShippingCostResolver
from modules.costing.unit_cost_service import UnitCostService
from modules.listing.listing_service import ListingService
from modules.listing.listing_validator import ListingValidator
from modules.listing.schemas import DesignBatchInput


def catalog() -> list[FactoryCostMatch]:
    return [
        FactoryCostMatch(
            supplier_code="LINGDIAN",
            factory_cost_cny=Decimal("38.00"),
            colors_count=24,
            width_cm=Decimal("30"),
            height_cm=Decimal("40"),
            framed=False,
            source_sheet="Sheet1",
            source_row=7,
        ),
        FactoryCostMatch(
            supplier_code="LINGDIAN",
            factory_cost_cny=Decimal("44.00"),
            colors_count=24,
            width_cm=Decimal("40"),
            height_cm=Decimal("50"),
            framed=False,
            source_sheet="Sheet1",
            source_row=10,
        ),
    ]


def service() -> ListingService:
    costing = CostingSettings(
        usd_cny_exchange_rate=Decimal("7.25"),
        exchange_rate_timestamp=datetime(2026, 9, 17, tzinfo=UTC),
    )
    return ListingService(
        factory_cost_resolver=FactoryCostResolver(),
        shipping_cost_resolver=ShippingCostResolver(costing),
        unit_cost_service=UnitCostService(costing),
        validator=ListingValidator(ListingSettings()),
    )


def design_batch(image: Path) -> DesignBatchInput:
    return DesignBatchInput.model_validate(
        {
            "designs": [
                {
                    "design_id": "DESIGN-CAT-000001",
                    "factory_design_code": "CAT000001",
                    "title_base": "Cat Portrait",
                    "theme": "Animals",
                    "main_image": str(image),
                    "available_variants": [
                        {
                            "width_cm": "30",
                            "height_cm": "40",
                            "colors_count": 24,
                            "framed": False,
                        },
                        {
                            "width_cm": "40",
                            "height_cm": "50",
                            "colors_count": 24,
                            "framed": False,
                        },
                        {
                            "width_cm": "20",
                            "height_cm": "20",
                            "colors_count": 60,
                            "framed": True,
                        },
                    ],
                }
            ]
        }
    )


def test_valid_listing_generates_two_quoted_skus_and_skips_no_quote(tmp_path: Path) -> None:
    image = tmp_path / "CAT000001.jpg"
    image.write_bytes(b"fixture")
    result = service().generate(design_batch(image), supplier_code="LINGDIAN", catalog=catalog())
    product = result.products[0]
    assert product.valid is True
    assert [sku.factory_sku for sku in product.skus] == [
        "PBN-CAT000001-3040-24-U",
        "PBN-CAT000001-4050-24-U",
    ]
    assert product.skus[1].factory_cost is not None
    assert product.skus[1].factory_cost.factory_cost_cny == Decimal("44.00")
    assert product.skus[1].unit_cost is not None
    assert product.skus[1].unit_cost.shipping_cost_usd == Decimal("4.00")
    assert any(issue.code == "NO_QUOTE_SKIPPED" for issue in result.issues)


def test_missing_main_image_fails_listing(tmp_path: Path) -> None:
    result = service().generate(
        design_batch(tmp_path / "missing.jpg"),
        supplier_code="LINGDIAN",
        catalog=catalog(),
    )
    assert result.products[0].valid is False
    assert any(issue.code == "MISSING_MAIN_IMAGE" for issue in result.issues)


def test_override_no_quote_generates_but_invalidates_sku(tmp_path: Path) -> None:
    image = tmp_path / "CAT000001.jpg"
    image.write_bytes(b"fixture")
    batch = design_batch(image)
    batch.designs[0].available_variants[-1].override_no_quote = True
    result = service().generate(batch, supplier_code="LINGDIAN", catalog=catalog())
    overridden = result.products[0].skus[-1]
    assert overridden.factory_sku == "PBN-CAT000001-2020-60-F"
    assert overridden.valid is False
    assert any(issue.code == "MISSING_FACTORY_COST" for issue in result.issues)

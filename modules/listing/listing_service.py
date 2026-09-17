from modules.costing.factory_cost_resolver import FactoryCostResolver
from modules.costing.schemas import FactoryCostMatch, MissingExchangeRateError
from modules.costing.shipping_cost_resolver import ShippingCostResolver
from modules.costing.unit_cost_service import UnitCostService
from modules.listing.listing_validator import ListingValidator
from modules.listing.schemas import (
    DesignBatchInput,
    ListingBatch,
    ListingIssue,
    ListingProduct,
    ListingSKU,
)
from modules.listing.sku_generator import generate_sku
from modules.listing.title_generator import generate_title


class ListingService:
    def __init__(
        self,
        *,
        factory_cost_resolver: FactoryCostResolver,
        shipping_cost_resolver: ShippingCostResolver,
        unit_cost_service: UnitCostService,
        validator: ListingValidator,
    ) -> None:
        self.factory_cost_resolver = factory_cost_resolver
        self.shipping_cost_resolver = shipping_cost_resolver
        self.unit_cost_service = unit_cost_service
        self.validator = validator

    def generate(
        self,
        design_batch: DesignBatchInput,
        *,
        supplier_code: str,
        catalog: list[FactoryCostMatch],
    ) -> ListingBatch:
        products: list[ListingProduct] = []
        batch_issues: list[ListingIssue] = []
        shipping = self.shipping_cost_resolver.resolve_estimate()

        for design in design_batch.designs:
            skus: list[ListingSKU] = []
            product_issues: list[ListingIssue] = []
            for variant in design.available_variants:
                factory_cost = self.factory_cost_resolver.resolve_from_catalog(
                    catalog,
                    supplier_code=supplier_code,
                    colors_count=variant.colors_count,
                    width_cm=variant.width_cm,
                    height_cm=variant.height_cm,
                    framed=variant.framed,
                )
                sku_code = generate_sku(
                    design.factory_design_code,
                    variant.width_cm,
                    variant.height_cm,
                    variant.colors_count,
                    variant.framed,
                )
                if factory_cost is None and not variant.override_no_quote:
                    product_issues.append(
                        ListingIssue(
                            severity="WARNING",
                            code="NO_QUOTE_SKIPPED",
                            message=(
                                "Requested variant has no valid factory quote and was not generated"
                            ),
                            design_id=design.design_id,
                            sku=sku_code,
                        )
                    )
                    continue

                unit_cost = None
                if factory_cost is not None:
                    try:
                        unit_cost = self.unit_cost_service.calculate(
                            factory_cost=factory_cost, shipping_cost=shipping
                        )
                    except MissingExchangeRateError as exc:
                        product_issues.append(
                            ListingIssue(
                                severity="ERROR",
                                code="MISSING_EXCHANGE_RATE",
                                message=str(exc),
                                design_id=design.design_id,
                                sku=sku_code,
                            )
                        )
                skus.append(
                    ListingSKU(
                        factory_sku=sku_code,
                        width_cm=variant.width_cm,
                        height_cm=variant.height_cm,
                        colors_count=variant.colors_count,
                        framed=variant.framed,
                        factory_cost=factory_cost,
                        shipping_cost=shipping,
                        unit_cost=unit_cost,
                    )
                )
            products.append(
                ListingProduct(
                    design_id=design.design_id,
                    factory_design_code=design.factory_design_code,
                    title=generate_title(design.title_base, design.theme),
                    theme=design.theme,
                    main_image=design.main_image,
                    additional_images=design.additional_images,
                    product_type=design.product_type,
                    target_market=design.target_market,
                    skus=skus,
                    issues=product_issues,
                )
            )
        return self.validator.validate(ListingBatch(products=products, issues=batch_issues))

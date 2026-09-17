from modules.listing.schemas import CanonicalListingRow, ListingProduct, ListingSKU


def to_canonical_row(product: ListingProduct, sku: ListingSKU) -> CanonicalListingRow:
    if sku.factory_cost is None or sku.shipping_cost is None or sku.unit_cost is None:
        raise ValueError(f"SKU {sku.factory_sku} is missing a complete cost chain")
    return CanonicalListingRow(
        design_id=product.design_id,
        factory_design_code=product.factory_design_code,
        title=product.title,
        theme=product.theme,
        product_type=product.product_type,
        target_market=product.target_market,
        main_image=str(product.main_image),
        additional_images="|".join(str(path) for path in product.additional_images),
        sku=sku.factory_sku,
        width_cm=sku.width_cm,
        height_cm=sku.height_cm,
        colors_count=sku.colors_count,
        framed=sku.framed,
        factory_cost_cny=sku.factory_cost.factory_cost_cny,
        shipping_cost_usd=sku.shipping_cost.amount_usd,
        unit_variable_cost_cny=sku.unit_cost.unit_variable_cost_cny,
    )

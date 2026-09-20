from modules.listing.schemas import CanonicalListingRow, ListingProduct, ListingSKU
from modules.listing.sku_generator import generate_spu_item_code


def to_canonical_row(product: ListingProduct, sku: ListingSKU) -> CanonicalListingRow:
    if sku.factory_cost is None or sku.shipping_cost is None or sku.unit_cost is None:
        raise ValueError(f"SKU {sku.factory_sku} is missing a complete cost chain")
    return CanonicalListingRow(
        design_id=product.design_id,
        factory_design_code=product.factory_design_code,
        spu_item_code=generate_spu_item_code(product.factory_design_code),
        title=product.title,
        title_zh=product.title_zh,
        theme=product.theme,
        product_type=product.product_type,
        target_market=product.target_market,
        main_image=str(product.main_image),
        additional_images="|".join(str(path) for path in product.additional_images),
        publish_image_refs=product.publish_image_refs,
        style_tags=product.style_tags,
        theme_tags=product.theme_tags,
        sensitive_attributes=product.sensitive_attributes,
        origin_country=product.origin_country,
        origin_province=product.origin_province,
        manufacturing_regions=product.manufacturing_regions,
        material=product.material,
        spu_frame_type=product.spu_frame_type,
        sku=sku.factory_sku,
        width_cm=sku.width_cm,
        height_cm=sku.height_cm,
        colors_count=sku.colors_count,
        framed=sku.framed,
        sku_image_ref=sku.sku_image_ref,
        declared_price_cny=sku.declared_price_cny,
        warehouse_inventory=sku.warehouse_inventory,
        package_length_cm=sku.package_length_cm,
        package_width_cm=sku.package_width_cm,
        package_height_cm=sku.package_height_cm,
        package_weight_g=sku.package_weight_g,
        max_units_per_box=sku.max_units_per_box,
        packaging_source=sku.packaging_source,
        packaging_source_hash=sku.packaging_source_hash,
        weight_source=sku.weight_source,
        weight_source_hash=sku.weight_source_hash,
        factory_cost_cny=sku.factory_cost.factory_cost_cny,
        shipping_cost_usd=sku.shipping_cost.amount_usd,
        unit_variable_cost_cny=sku.unit_cost.unit_variable_cost_cny,
    )

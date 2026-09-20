import hashlib
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.config import Settings
from models import SKU, Design, FactoryCost, Product, Supplier
from models.enums import (
    LabelServiceCostStatus,
    ProductStatus,
    ShippingCostType,
    ValidationStatus,
)
from modules.listing.sku_generator import generate_sku, generate_spu_item_code


class ProductIntakeError(RuntimeError):
    """Raised when a product intake cannot be linked to master data safely."""


class ProductIntakeService:
    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory

    async def run(
        self,
        *,
        intake_path: Path,
        supplier_code: str,
        commit: bool,
    ) -> dict[str, Any]:
        path = intake_path.expanduser().resolve()
        payload = self._load_payload(path)
        parsed = self._parse_payload(payload)
        normalized_supplier = supplier_code.strip().upper()
        if not normalized_supplier:
            raise ProductIntakeError("supplier_code cannot be blank")

        async with self.session_factory() as session:
            if commit:
                async with session.begin():
                    return await self._apply(
                        session,
                        parsed=parsed,
                        raw_payload=payload,
                        source_path=path,
                        supplier_code=normalized_supplier,
                        commit=True,
                    )
            return await self._apply(
                session,
                parsed=parsed,
                raw_payload=payload,
                source_path=path,
                supplier_code=normalized_supplier,
                commit=False,
            )

    @staticmethod
    def _load_payload(path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise ProductIntakeError(f"Product intake does not exist: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ProductIntakeError(f"Cannot read product intake: {exc}") from exc
        if not isinstance(payload, dict):
            raise ProductIntakeError("Product intake root must be an object")
        return payload

    @staticmethod
    def _parse_payload(payload: dict[str, Any]) -> dict[str, Any]:
        identifiers = _object(payload, "identifiers")
        content = _object(payload, "proposed_content")
        factory_design_code = _required_text(identifiers, "factory_design_code").upper()
        product_code = _required_text(identifiers, "internal_spu_item_code").upper()
        expected_product_code = generate_spu_item_code(factory_design_code)
        if product_code != expected_product_code:
            raise ProductIntakeError(
                f"Internal SPU {product_code} does not match generated code {expected_product_code}"
            )

        raw_variants = payload.get("known_variants")
        if not isinstance(raw_variants, list) or not raw_variants:
            raise ProductIntakeError("known_variants must contain at least one variant")
        variants: list[dict[str, Any]] = []
        seen_skus: set[str] = set()
        for index, raw_variant in enumerate(raw_variants, start=1):
            if not isinstance(raw_variant, dict):
                raise ProductIntakeError(f"known_variants entry {index} must be an object")
            try:
                width = Decimal(str(raw_variant["width_cm"]))
                height = Decimal(str(raw_variant["height_cm"]))
                colors = int(raw_variant["colors_count"])
                framed = raw_variant["framed"]
            except (KeyError, TypeError, ValueError) as exc:
                raise ProductIntakeError(f"Invalid known_variants entry {index}") from exc
            if not isinstance(framed, bool) or width <= 0 or height <= 0 or colors <= 0:
                raise ProductIntakeError(f"Invalid known_variants entry {index}")
            sku_code = generate_sku(factory_design_code, width, height, colors, framed)
            if sku_code in seen_skus:
                raise ProductIntakeError(f"Duplicate generated SKU: {sku_code}")
            seen_skus.add(sku_code)
            variants.append(
                {
                    "sku_code": sku_code,
                    "width_cm": width,
                    "height_cm": height,
                    "colors_count": colors,
                    "framed": framed,
                }
            )

        source_assets = payload.get("source_assets", [])
        if not isinstance(source_assets, list):
            raise ProductIntakeError("source_assets must be a list")
        valid_assets = [asset for asset in source_assets if isinstance(asset, dict)]
        main_image = next(
            (
                str(asset["path"])
                for asset in valid_assets
                if asset.get("role") == "MAIN_IMAGE_CANDIDATE" and asset.get("path")
            ),
            None,
        )
        additional_images = [
            str(asset["path"])
            for asset in valid_assets
            if asset.get("path") and str(asset["path"]) != main_image
        ]
        title = str(
            content.get("title_en")
            or _object(payload, "submission").get("title_displayed")
            or product_code
        ).strip()
        theme_tags = _string_list(content.get("theme_tags"))
        style_tags = _string_list(content.get("style_tags"))
        return {
            "factory_design_code": factory_design_code,
            "design_code": f"DESIGN-{factory_design_code}",
            "product_code": product_code,
            "title": title,
            "theme": theme_tags[0] if theme_tags else None,
            "sub_theme": style_tags[0] if style_tags else None,
            "main_image": main_image,
            "additional_images": additional_images,
            "variants": variants,
        }

    async def _apply(
        self,
        session: AsyncSession,
        *,
        parsed: dict[str, Any],
        raw_payload: dict[str, Any],
        source_path: Path,
        supplier_code: str,
        commit: bool,
    ) -> dict[str, Any]:
        supplier = await session.scalar(
            select(Supplier).where(Supplier.supplier_code == supplier_code)
        )
        if supplier is None:
            raise ProductIntakeError(f"Supplier is not configured: {supplier_code}")

        design = await session.scalar(
            select(Design).where(
                or_(
                    Design.design_code == parsed["design_code"],
                    Design.factory_design_code == parsed["factory_design_code"],
                )
            )
        )
        if design is not None and (
            design.design_code != parsed["design_code"]
            or design.factory_design_code != parsed["factory_design_code"]
        ):
            raise ProductIntakeError("Design code collision detected")

        product = await session.scalar(
            select(Product).where(Product.internal_product_code == parsed["product_code"])
        )
        if product is not None and design is not None and product.design_id != design.id:
            raise ProductIntakeError("Product code is already linked to another design")

        variant_codes = [variant["sku_code"] for variant in parsed["variants"]]
        existing_skus = (
            await session.scalars(
                select(SKU).where(
                    SKU.supplier_id == supplier.id,
                    SKU.factory_sku.in_(variant_codes),
                )
            )
        ).all()
        existing_by_code = {sku.factory_sku: sku for sku in existing_skus}
        cost_by_code = await self._resolve_costs(
            session,
            supplier_id=supplier.id,
            variants=parsed["variants"],
        )
        missing_costs = sorted(set(variant_codes) - set(cost_by_code))
        if missing_costs:
            raise ProductIntakeError(
                "No active factory quote for variants: " + ", ".join(missing_costs)
            )

        result: dict[str, Any] = {
            "design_code": parsed["design_code"],
            "factory_design_code": parsed["factory_design_code"],
            "product_code": parsed["product_code"],
            "supplier_code": supplier_code,
            "sku_count": len(variant_codes),
            "inserted": 0,
            "updated": 0,
            "unchanged": 0,
            "committed": commit,
        }
        if not commit:
            result["inserted"] = (
                int(design is None)
                + int(product is None)
                + sum(code not in existing_by_code for code in variant_codes)
            )
            result["unchanged"] = sum(code in existing_by_code for code in variant_codes)
            return result

        source_metadata = {
            "intake_file": source_path.name,
            "intake_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
            "intake_status": raw_payload.get("status"),
            "source_assets": raw_payload.get("source_assets", []),
        }
        if design is None:
            design = Design(
                design_code=parsed["design_code"],
                factory_design_code=parsed["factory_design_code"],
                name=parsed["title"],
                theme=parsed["theme"],
                sub_theme=parsed["sub_theme"],
                image_path=parsed["main_image"],
                additional_image_paths=parsed["additional_images"],
                is_customizable=False,
                requires_manual_review=bool(raw_payload.get("blocking_fields")),
                special_handling_notes=(
                    "Product submitted; source and compliance evidence pending review."
                ),
                extra_data=source_metadata,
            )
            session.add(design)
            await session.flush()
            result["inserted"] += 1

        if product is None:
            product = Product(
                design_id=design.id,
                internal_product_code=parsed["product_code"],
                title=parsed["title"],
                status=ProductStatus.READY,
                extra_data={
                    "marketplace": raw_payload.get("marketplace"),
                    "store_mode": raw_payload.get("store_mode"),
                    "category_path": raw_payload.get("category_path"),
                    "publishing_system": raw_payload.get("publishing_system"),
                    "fulfillment_system": raw_payload.get("fulfillment_system"),
                    "submission": raw_payload.get("submission", {}),
                },
            )
            session.add(product)
            await session.flush()
            result["inserted"] += 1

        for variant in parsed["variants"]:
            sku_code = variant["sku_code"]
            existing = existing_by_code.get(sku_code)
            cost = cost_by_code[sku_code]
            values: dict[str, Any] = {
                "product_id": product.id,
                "design_id": design.id,
                "supplier_id": supplier.id,
                "temu_sku": sku_code,
                "size_label": f"{variant['width_cm']:g}x{variant['height_cm']:g}cm",
                "width_cm": variant["width_cm"],
                "height_cm": variant["height_cm"],
                "colors_count": variant["colors_count"],
                "framed": variant["framed"],
                "image_path": parsed["main_image"],
                "resolved_factory_cost_id": cost.id,
                "shipping_cost_usd": self.settings.costing.estimated_shipping_cost_usd,
                "shipping_cost_type": ShippingCostType.ESTIMATED_AVERAGE.value,
                "label_service_cost_cny": self.settings.costing.label_service_cost_cny,
                "label_service_cost_status": LabelServiceCostStatus.CONFIRMED.value,
            }
            if existing is None:
                session.add(SKU(factory_sku=sku_code, **values))
                result["inserted"] += 1
                continue
            changed = any(getattr(existing, key) != value for key, value in values.items())
            if not changed:
                result["unchanged"] += 1
                continue
            for key, value in values.items():
                setattr(existing, key, value)
            result["updated"] += 1
        return result

    @staticmethod
    async def _resolve_costs(
        session: AsyncSession,
        *,
        supplier_id: Any,
        variants: list[dict[str, Any]],
    ) -> dict[str, FactoryCost]:
        today = date.today()
        resolved: dict[str, FactoryCost] = {}
        for variant in variants:
            statement = (
                select(FactoryCost)
                .where(
                    FactoryCost.supplier_id == supplier_id,
                    FactoryCost.colors_count == variant["colors_count"],
                    FactoryCost.width_cm == variant["width_cm"],
                    FactoryCost.height_cm == variant["height_cm"],
                    FactoryCost.framed == variant["framed"],
                    FactoryCost.currency == "CNY",
                    FactoryCost.effective_from <= today,
                    or_(FactoryCost.effective_to.is_(None), FactoryCost.effective_to >= today),
                    FactoryCost.validation_status != ValidationStatus.INVALID,
                )
                .order_by(FactoryCost.effective_from.desc())
                .limit(1)
            )
            cost = await session.scalar(statement)
            if cost is not None:
                resolved[variant["sku_code"]] = cost
        return resolved


def _object(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise ProductIntakeError(f"{key} must be an object")
    return value


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ProductIntakeError(f"{key} must be a non-empty string")
    return value.strip()


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]

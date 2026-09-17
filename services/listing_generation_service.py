import hashlib
import json
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.config import Settings
from integrations.excel.listing_validation_writer import ListingValidationWriter
from integrations.temu.template_adapter import TemuExcelTemplateAdapter, TemuTemplateError
from models import FactoryCost, Supplier
from models.enums import ValidationStatus
from modules.costing.factory_cost_resolver import FactoryCostResolver
from modules.costing.schemas import FactoryCostMatch
from modules.costing.shipping_cost_resolver import ShippingCostResolver
from modules.costing.unit_cost_service import UnitCostService
from modules.listing.attribute_mapper import to_canonical_row
from modules.listing.image_mapper import normalize_image_path
from modules.listing.listing_service import ListingService
from modules.listing.listing_validator import ListingValidator
from modules.listing.schemas import DesignBatchInput, ListingBatch


class ListingGenerationError(RuntimeError):
    pass


class ListingGenerationService:
    def __init__(
        self,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        project_root: Path,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.project_root = project_root
        self.report_writer = ListingValidationWriter(settings.reports, project_root)
        self.template_adapter = TemuExcelTemplateAdapter(settings.reports, project_root)

    async def run(
        self,
        *,
        design_batch_path: Path,
        template_path: Path,
        mapping_path: Path | None,
        supplier_code: str,
        output_root: Path,
        commit: bool,
    ) -> dict[str, Any]:
        design_batch_file = design_batch_path.expanduser().resolve()
        template_file = template_path.expanduser().resolve()
        batch_id = str(uuid.uuid4())
        output_dir = output_root.expanduser().resolve() / batch_id
        output_dir.mkdir(parents=True, exist_ok=True)
        design_batch = self._read_design_batch(design_batch_file)
        catalog = await self._load_catalog(supplier_code)
        listing_service = ListingService(
            factory_cost_resolver=FactoryCostResolver(),
            shipping_cost_resolver=ShippingCostResolver(self.settings.costing),
            unit_cost_service=UnitCostService(self.settings.costing),
            validator=ListingValidator(self.settings.listing),
        )
        listing = listing_service.generate(
            design_batch, supplier_code=supplier_code, catalog=catalog
        )

        template_hash = self._sha256(template_file) if template_file.is_file() else None
        template_error: str | None = None
        if mapping_path is None:
            template_error = "A reviewed real Temu template mapping has not been provided"
        else:
            try:
                self.template_adapter.validate_mapping(template_file, mapping_path)
            except TemuTemplateError as exc:
                template_error = str(exc)

        payload = self._validation_payload(listing, template_error)
        report_path = self.report_writer.write(payload, output_dir / "listing_validation.xlsx")
        export_path: Path | None = None
        if commit:
            if template_error is not None:
                raise ListingGenerationError(template_error)
            if any(issue["severity"] == "ERROR" for issue in payload["issues"]):
                raise ListingGenerationError(
                    "Pre-flight validation failed; no formal Temu upload workbook was created"
                )
            assert mapping_path is not None
            rows = [
                to_canonical_row(product, sku)
                for product in listing.products
                if product.valid
                for sku in product.skus
                if sku.valid
            ]
            export_path = self.template_adapter.export(
                template_path=template_file,
                mapping_path=mapping_path,
                rows=rows,
                output_path=output_dir / "temu_batch_listing.xlsx",
            )

        manifest = {
            "batch_id": batch_id,
            "mode": "COMMIT" if commit else "DRY_RUN",
            "design_count": len(listing.products),
            "product_count": len(listing.products),
            "sku_count": sum(len(product.skus) for product in listing.products),
            "created_at": datetime.now(UTC).isoformat(),
            "source_template": str(template_file),
            "template_hash": template_hash,
            "template_mapping": str(mapping_path.resolve()) if mapping_path else None,
            "template_error": template_error,
            "validation_report": str(report_path),
            "temu_batch_listing": str(export_path) if export_path else None,
        }
        manifest_path = output_dir / "listing_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {"manifest": manifest, "payload": payload, "manifest_path": manifest_path}

    def _read_design_batch(self, path: Path) -> DesignBatchInput:
        if not path.is_file():
            raise ListingGenerationError(f"Design batch does not exist: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            batch = DesignBatchInput.model_validate(payload)
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            raise ListingGenerationError(f"Cannot read design batch: {exc}") from exc
        for design in batch.designs:
            design.main_image = normalize_image_path(design.main_image, base_dir=path.parent)
            design.additional_images = [
                normalize_image_path(image, base_dir=path.parent)
                for image in design.additional_images
            ]
        return batch

    async def _load_catalog(self, supplier_code: str) -> list[FactoryCostMatch]:
        today = date.today()
        statement = (
            select(FactoryCost, Supplier.supplier_code)
            .join(Supplier, FactoryCost.supplier_id == Supplier.id)
            .where(
                Supplier.supplier_code == supplier_code.upper(),
                FactoryCost.effective_from <= today,
                or_(FactoryCost.effective_to.is_(None), FactoryCost.effective_to >= today),
                FactoryCost.validation_status != ValidationStatus.INVALID,
                FactoryCost.currency == "CNY",
            )
        )
        async with self.session_factory() as session:
            rows = (await session.execute(statement)).all()
        return [
            FactoryCostMatch(
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
            for cost, code in rows
        ]

    @staticmethod
    def _validation_payload(listing: ListingBatch, template_error: str | None) -> dict[str, Any]:
        products: list[dict[str, Any]] = []
        skus: list[dict[str, Any]] = []
        valid_product_count = 0
        valid_sku_count = 0
        issues = [issue.model_dump(mode="json") for issue in listing.issues]
        if template_error:
            issues.append(
                {
                    "severity": "ERROR",
                    "code": "TEMU_TEMPLATE_NOT_READY",
                    "design_id": "BATCH",
                    "sku": None,
                    "message": template_error,
                }
            )
        for product in listing.products:
            valid_product_count += int(product.valid)
            product_valid_sku_count = sum(sku.valid for sku in product.skus)
            products.append(
                {
                    "design_id": product.design_id,
                    "factory_design_code": product.factory_design_code,
                    "title": product.title,
                    "valid": "YES" if product.valid else "NO",
                    "sku_count": len(product.skus),
                    "valid_sku_count": product_valid_sku_count,
                    "main_image": str(product.main_image),
                }
            )
            for sku in product.skus:
                valid_sku_count += int(sku.valid)
                skus.append(
                    {
                        "design_id": product.design_id,
                        "sku": sku.factory_sku,
                        "size": f"{sku.width_cm}x{sku.height_cm}",
                        "colors_count": sku.colors_count,
                        "framed": "YES" if sku.framed else "NO",
                        "factory_cost_cny": (
                            str(sku.factory_cost.factory_cost_cny)
                            if sku.factory_cost is not None
                            else None
                        ),
                        "shipping_cost_usd": (
                            str(sku.shipping_cost.amount_usd)
                            if sku.shipping_cost is not None
                            else None
                        ),
                        "exchange_rate": (
                            str(sku.unit_cost.exchange_rate) if sku.unit_cost is not None else None
                        ),
                        "unit_variable_cost_cny": (
                            str(sku.unit_cost.unit_variable_cost_cny)
                            if sku.unit_cost is not None
                            else None
                        ),
                        "valid": "YES" if sku.valid else "NO",
                    }
                )
        summary = {
            "designs": len(products),
            "products": len(products),
            "skus": len(skus),
            "valid_products": valid_product_count,
            "invalid_products": len(products) - valid_product_count,
            "valid_skus": valid_sku_count,
            "invalid_skus": len(skus) - valid_sku_count,
            "missing_images": sum(issue["code"] == "MISSING_MAIN_IMAGE" for issue in issues),
            "missing_factory_cost": sum(
                issue["code"] == "MISSING_FACTORY_COST" for issue in issues
            ),
            "invalid_attributes": sum(
                issue["code"]
                in {
                    "INVALID_SIZE",
                    "INVALID_COLORS_COUNT",
                    "INVALID_FACTORY_DESIGN_CODE",
                }
                for issue in issues
            ),
            "template_ready": "YES" if template_error is None else "NO",
        }
        return {"summary": summary, "products": products, "skus": skus, "issues": issues}

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

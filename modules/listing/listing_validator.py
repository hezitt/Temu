from collections import Counter

from core.config import ListingSettings
from integrations.fangguo.naming import (
    InvalidFactoryDesignCodeError,
    validate_factory_design_code,
)
from modules.listing.schemas import ListingBatch, ListingIssue, ListingProduct


class ListingValidator:
    def __init__(self, settings: ListingSettings) -> None:
        self.settings = settings

    def validate(self, batch: ListingBatch) -> ListingBatch:
        all_skus = [sku.factory_sku for product in batch.products for sku in product.skus]
        duplicate_skus = {sku for sku, count in Counter(all_skus).items() if count > 1}
        duplicate_design_ids = {
            value
            for value, count in Counter(product.design_id for product in batch.products).items()
            if count > 1
        }
        duplicate_factory_codes = {
            value
            for value, count in Counter(
                product.factory_design_code for product in batch.products
            ).items()
            if count > 1
        }
        batch_issues = list(batch.issues)
        validated_products: list[ListingProduct] = []

        for product in batch.products:
            issues = list(product.issues)
            self._validate_product(product, issues)
            if product.design_id in duplicate_design_ids:
                issues.append(
                    self._issue(product, "DUPLICATE_DESIGN_ID", "Design ID must be unique")
                )
            if product.factory_design_code in duplicate_factory_codes:
                issues.append(
                    self._issue(
                        product,
                        "DUPLICATE_FACTORY_DESIGN_CODE",
                        "Factory Design Code must be unique",
                    )
                )
            for sku in product.skus:
                sku.valid = True
                if sku.factory_sku in duplicate_skus:
                    issues.append(
                        self._issue(
                            product,
                            "DUPLICATE_SKU",
                            f"Duplicate SKU: {sku.factory_sku}",
                            sku.factory_sku,
                        )
                    )
                    sku.valid = False
                if sku.factory_cost is None:
                    issues.append(
                        self._issue(
                            product,
                            "MISSING_FACTORY_COST",
                            "SKU has no matching valid factory quote",
                            sku.factory_sku,
                        )
                    )
                    sku.valid = False
                if sku.shipping_cost is None:
                    issues.append(
                        self._issue(
                            product,
                            "MISSING_SHIPPING_COST",
                            "SKU has no shipping estimate",
                            sku.factory_sku,
                        )
                    )
                    sku.valid = False
                if sku.unit_cost is None:
                    issues.append(
                        self._issue(
                            product,
                            "INCOMPLETE_UNIT_COST",
                            "SKU lacks a complete CNY unit variable cost",
                            sku.factory_sku,
                        )
                    )
                    sku.valid = False
                if sku.width_cm <= 0 or sku.height_cm <= 0:
                    issues.append(
                        self._issue(
                            product,
                            "INVALID_SIZE",
                            "SKU dimensions must be positive",
                            sku.factory_sku,
                        )
                    )
                    sku.valid = False
                if sku.colors_count <= 0:
                    issues.append(
                        self._issue(
                            product,
                            "INVALID_COLORS_COUNT",
                            "SKU colors_count must be positive",
                            sku.factory_sku,
                        )
                    )
                    sku.valid = False

            if not any(sku.valid for sku in product.skus):
                issues.append(
                    self._issue(
                        product,
                        "NO_VALID_SKU",
                        "Product must have at least one valid SKU",
                    )
                )
            product.issues = self._deduplicate(issues)
            product.valid = not any(
                issue.severity == "ERROR" and issue.sku is None for issue in product.issues
            ) and any(sku.valid for sku in product.skus)
            batch_issues.extend(product.issues)
            validated_products.append(product)

        batch.products = validated_products
        batch.issues = self._deduplicate(batch_issues)
        return batch

    def _validate_product(self, product: ListingProduct, issues: list[ListingIssue]) -> None:
        for value, code, message in (
            (product.design_id, "MISSING_DESIGN_ID", "Design ID is required"),
            (
                product.factory_design_code,
                "MISSING_FACTORY_DESIGN_CODE",
                "Factory Design Code is required",
            ),
            (product.title, "MISSING_TITLE", "Title is required"),
            (product.product_type, "MISSING_PRODUCT_TYPE", "Product type is required"),
            (product.target_market, "MISSING_TARGET_MARKET", "Target market is required"),
        ):
            if not value:
                issues.append(self._issue(product, code, message))
        if self.settings.require_existing_main_image and not product.main_image.is_file():
            issues.append(
                self._issue(
                    product,
                    "MISSING_MAIN_IMAGE",
                    f"Main image does not exist: {product.main_image}",
                )
            )
        try:
            validate_factory_design_code(product.factory_design_code)
        except InvalidFactoryDesignCodeError as exc:
            issues.append(self._issue(product, "INVALID_FACTORY_DESIGN_CODE", str(exc)))

    @staticmethod
    def _issue(
        product: ListingProduct, code: str, message: str, sku: str | None = None
    ) -> ListingIssue:
        return ListingIssue(
            severity="ERROR", code=code, message=message, design_id=product.design_id, sku=sku
        )

    @staticmethod
    def _deduplicate(issues: list[ListingIssue]) -> list[ListingIssue]:
        result: list[ListingIssue] = []
        seen: set[tuple[str, str, str | None]] = set()
        for issue in issues:
            key = (issue.design_id, issue.code, issue.sku)
            if key not in seen:
                result.append(issue)
                seen.add(key)
        return result

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from models import SKU, Product, Supplier, TemuListing
from models.enums import ListingStatus
from modules.listing.external_ids import DianxiaomiListingObservation


class ListingExternalIdSyncError(RuntimeError):
    """Raised when an observed platform identifier cannot be linked safely."""


class ListingExternalIdService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def run(
        self,
        *,
        observation: DianxiaomiListingObservation,
        supplier_code: str,
        store_code: str,
        commit: bool,
    ) -> dict[str, Any]:
        normalized_supplier = supplier_code.strip().upper()
        normalized_store = store_code.strip().upper()
        if not normalized_supplier:
            raise ListingExternalIdSyncError("supplier_code cannot be blank")
        if not normalized_store:
            raise ListingExternalIdSyncError("store_code cannot be blank")

        async with self.session_factory() as session:
            if commit:
                async with session.begin():
                    return await self._sync(
                        session,
                        observation=observation,
                        supplier_code=normalized_supplier,
                        store_code=normalized_store,
                        commit=True,
                    )
            return await self._sync(
                session,
                observation=observation,
                supplier_code=normalized_supplier,
                store_code=normalized_store,
                commit=False,
            )

    @staticmethod
    async def _sync(
        session: AsyncSession,
        *,
        observation: DianxiaomiListingObservation,
        supplier_code: str,
        store_code: str,
        commit: bool,
    ) -> dict[str, Any]:
        supplier = await session.scalar(
            select(Supplier).where(Supplier.supplier_code == supplier_code)
        )
        if supplier is None:
            raise ListingExternalIdSyncError(
                f"Supplier is not configured: {supplier_code}"
            )

        requested_codes = [mapping.sku_item_code for mapping in observation.sku_mappings]
        sku_rows = (
            await session.scalars(
                select(SKU)
                .join(Product, SKU.product_id == Product.id)
                .where(
                    SKU.supplier_id == supplier.id,
                    Product.internal_product_code
                    == observation.internal_spu_item_code,
                    SKU.factory_sku.in_(requested_codes),
                )
            )
        ).all()
        sku_by_code = {sku.factory_sku: sku for sku in sku_rows}
        missing_codes = sorted(set(requested_codes) - set(sku_by_code))
        if missing_codes:
            raise ListingExternalIdSyncError(
                "Cannot link observed IDs; internal SKUs are missing for product "
                f"{observation.internal_spu_item_code}: {', '.join(missing_codes)}"
            )

        sku_ids = [sku.id for sku in sku_rows]
        existing_rows = (
            await session.scalars(
                select(TemuListing).where(
                    TemuListing.store_code == store_code,
                    TemuListing.sku_id.in_(sku_ids),
                )
            )
        ).all()
        existing_by_sku_id = {row.sku_id: row for row in existing_rows}
        await ListingExternalIdService._ensure_no_external_id_collision(
            session,
            observation=observation,
            store_code=store_code,
            sku_by_code=sku_by_code,
        )

        synced_at = datetime.now(UTC)
        result: dict[str, Any] = {
            "internal_spu_item_code": observation.internal_spu_item_code,
            "dianxiaomi_spu_id": observation.dianxiaomi_spu_id,
            "temu_skc_id": observation.temu_skc_id,
            "store_code": store_code,
            "supplier_code": supplier_code,
            "sku_count": len(observation.sku_mappings),
            "inserted": 0,
            "updated": 0,
            "unchanged": 0,
            "committed": commit,
            "seller_center_confirmation_pending": (
                observation.seller_center_confirmation_pending
            ),
        }
        raw_payload = {
            "observation": observation.raw_payload,
            "source": {
                "file_name": observation.source_file_name,
                "sha256": observation.source_sha256,
            },
        }

        for mapping in observation.sku_mappings:
            sku = sku_by_code[mapping.sku_item_code]
            existing = existing_by_sku_id.get(sku.id)
            values: dict[str, Any] = {
                "marketplace": observation.marketplace,
                "dianxiaomi_spu_id": observation.dianxiaomi_spu_id,
                "temu_spu": (
                    observation.temu_spu_id
                    if observation.temu_spu_id is not None
                    else existing.temu_spu if existing is not None else None
                ),
                "temu_skc_id": observation.temu_skc_id,
                "temu_sku_id": mapping.temu_sku_id,
                "platform_review_status": observation.review_status,
                "platform_lifecycle_status": observation.lifecycle_status,
                "external_id_source": observation.submission_channel,
                "external_id_observed_at": observation.observed_at,
                "status": _listing_status(observation),
                "raw_payload": raw_payload,
            }
            if existing is None:
                result["inserted"] += 1
                if commit:
                    session.add(
                        TemuListing(
                            sku_id=sku.id,
                            store_code=store_code,
                            submitted_at=observation.observed_at,
                            last_synced_at=synced_at,
                            **values,
                        )
                    )
                continue

            changed = any(
                not _values_equal(getattr(existing, key), value)
                for key, value in values.items()
            )
            if not changed:
                result["unchanged"] += 1
                continue
            result["updated"] += 1
            if commit:
                for key, value in values.items():
                    setattr(existing, key, value)
                if existing.submitted_at is None:
                    existing.submitted_at = observation.observed_at
                existing.last_synced_at = synced_at

        return result

    @staticmethod
    async def _ensure_no_external_id_collision(
        session: AsyncSession,
        *,
        observation: DianxiaomiListingObservation,
        store_code: str,
        sku_by_code: dict[str, SKU],
    ) -> None:
        intended_sku_by_temu_id: dict[str, UUID] = {
            mapping.temu_sku_id: sku_by_code[mapping.sku_item_code].id
            for mapping in observation.sku_mappings
        }
        rows = (
            await session.scalars(
                select(TemuListing).where(
                    TemuListing.store_code == store_code,
                    TemuListing.temu_sku_id.in_(intended_sku_by_temu_id),
                )
            )
        ).all()
        for row in rows:
            assert row.temu_sku_id is not None
            intended_sku_id = intended_sku_by_temu_id[row.temu_sku_id]
            if row.sku_id != intended_sku_id:
                raise ListingExternalIdSyncError(
                    "Temu SKU ID collision in store "
                    f"{store_code}: {row.temu_sku_id} is already linked to another SKU"
                )


def _listing_status(observation: DianxiaomiListingObservation) -> ListingStatus:
    review_status = (observation.review_status or "").strip().upper()
    lifecycle_status = (observation.lifecycle_status or "").strip().upper()
    if review_status in {"REJECTED", "FAILED", "FAIL"}:
        return ListingStatus.REJECTED
    if lifecycle_status in {"ACTIVE", "ONLINE", "ON_SALE", "PUBLISHED"}:
        return ListingStatus.ACTIVE
    if lifecycle_status in {"INACTIVE", "OFFLINE", "ARCHIVED"}:
        return ListingStatus.INACTIVE
    if review_status in {
        "PENDING",
        "SUBMITTED",
        "UNDER_REVIEW",
        "REVIEWING",
        "APPROVED",
        "PASSED",
        "PASS",
    }:
        return ListingStatus.SUBMITTED
    return ListingStatus.UNKNOWN


def _values_equal(current: object, observed: object) -> bool:
    if isinstance(current, datetime) and isinstance(observed, datetime):
        current_utc = (
            current.replace(tzinfo=UTC)
            if current.tzinfo is None
            else current.astimezone(UTC)
        )
        observed_utc = (
            observed.replace(tzinfo=UTC)
            if observed.tzinfo is None
            else observed.astimezone(UTC)
        )
        return current_utc == observed_utc
    return current == observed

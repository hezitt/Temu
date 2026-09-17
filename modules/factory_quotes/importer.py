import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import SupplierProfile
from models import AuditLog, FactoryCost, FactoryQuoteRow, ImportBatch, Supplier
from models.enums import (
    AuditStatus,
    CostCompletenessStatus,
    ImportRowStatus,
    ImportStatus,
    ImportType,
    ValidationStatus,
)
from modules.factory_quotes.schemas import (
    DuplicateFileError,
    ImportPlan,
    NormalizedQuote,
    RowStatus,
)

SUCCESSFUL_BATCH_STATUSES = {
    ImportStatus.COMPLETED,
    ImportStatus.COMPLETED_WITH_ERRORS,
}


def _cost_key(record: NormalizedQuote) -> tuple[object, ...]:
    assert record.colors_count is not None
    assert record.width_cm is not None
    assert record.height_cm is not None
    return (
        record.product_type,
        record.colors_count,
        record.width_cm,
        record.height_cm,
        record.variant_type.value == "FRAMED",
    )


def _cost_snapshot(cost: FactoryCost) -> dict[str, object]:
    return {
        "id": str(cost.id),
        "product_type": cost.product_type,
        "colors_count": cost.colors_count,
        "size_code": cost.size_code,
        "width_cm": str(cost.width_cm),
        "height_cm": str(cost.height_cm),
        "framed": cost.framed,
        "base_product_cost": str(cost.base_product_cost),
        "currency": cost.currency,
        "shipping_included": cost.shipping_included,
        "effective_from": cost.effective_from.isoformat(),
        "effective_to": cost.effective_to.isoformat() if cost.effective_to else None,
        "validation_status": cost.validation_status.value,
        "cost_completeness_status": cost.cost_completeness_status.value,
    }


class FactoryQuoteImporter:
    async def supplier_for_code(self, session: AsyncSession, supplier_code: str) -> Supplier | None:
        result = await session.execute(
            select(Supplier).where(Supplier.supplier_code == supplier_code.upper())
        )
        return result.scalar_one_or_none()

    async def assert_file_not_imported(
        self,
        session: AsyncSession,
        supplier: Supplier | None,
        source_sha256: str,
        force: bool,
    ) -> None:
        if supplier is None or force:
            return
        result = await session.execute(
            select(ImportBatch.id).where(
                ImportBatch.supplier_id == supplier.id,
                ImportBatch.source_sha256 == source_sha256,
                ImportBatch.status.in_(SUCCESSFUL_BATCH_STATUSES),
            )
        )
        if result.first() is not None:
            raise DuplicateFileError(
                "This file has already been imported for this supplier. "
                "Use --force to reprocess it."
            )

    async def plan(
        self,
        session: AsyncSession,
        supplier_code: str,
        source_sha256: str,
        records: list[NormalizedQuote],
        force: bool,
    ) -> ImportPlan:
        supplier = await self.supplier_for_code(session, supplier_code)
        await self.assert_file_not_imported(session, supplier, source_sha256, force)
        importable = [record for record in records if record.is_importable]
        plan = ImportPlan()
        if supplier is None:
            plan.insert_count = len(importable)
            return plan

        existing = await self._current_costs(session, supplier.id)
        by_key = {_cost_key_from_model(cost): cost for cost in existing}
        for record in importable:
            current = by_key.get(_cost_key(record))
            if current is None:
                plan.insert_count += 1
            elif self._same_cost(current, record):
                plan.unchanged_count += 1
            else:
                plan.update_count += 1
        return plan

    async def commit(
        self,
        session: AsyncSession,
        *,
        batch_id: uuid.UUID,
        supplier_code: str,
        supplier_profile: SupplierProfile,
        source_filename: str,
        source_sha256: str,
        source_sheet: str,
        effective_date: date,
        records: list[NormalizedQuote],
        force: bool,
        report_path: str,
        started_at: datetime,
    ) -> ImportPlan:
        async with session.begin():
            supplier = await self.supplier_for_code(session, supplier_code)
            await self.assert_file_not_imported(session, supplier, source_sha256, force)
            if supplier is None:
                supplier = Supplier(
                    supplier_code=supplier_code.upper(),
                    name=supplier_profile.name,
                    currency=supplier_profile.currency,
                    country_code=supplier_profile.country_code,
                    timezone=supplier_profile.timezone,
                )
                session.add(supplier)
                await session.flush()

            counts = _row_counts(records)
            batch = ImportBatch(
                id=batch_id,
                supplier_id=supplier.id,
                import_type=ImportType.FACTORY_QUOTE,
                source_file_name=source_filename,
                source_sha256=source_sha256,
                source_sheet=source_sheet,
                status=ImportStatus.PROCESSING,
                row_count=len(records),
                success_count=counts[RowStatus.VALID] + counts[RowStatus.WARNING],
                warning_count=counts[RowStatus.WARNING],
                error_count=counts[RowStatus.ERROR],
                skipped_count=counts[RowStatus.SKIPPED],
                started_at=started_at,
                correlation_id=batch_id,
                error_report_path=report_path,
                extra_data={"force": force, "effective_date": effective_date.isoformat()},
            )
            session.add(batch)
            await session.flush()

            for record in records:
                session.add(self._raw_row(batch, supplier, record))

            existing = await self._current_costs(session, supplier.id)
            by_key = {_cost_key_from_model(cost): cost for cost in existing}
            plan = ImportPlan()
            for record in (item for item in records if item.is_importable):
                key = _cost_key(record)
                current = by_key.get(key)
                if current is None:
                    new_cost = self._new_cost(
                        supplier=supplier,
                        batch=batch,
                        record=record,
                        effective_date=effective_date,
                    )
                    session.add(new_cost)
                    await session.flush()
                    by_key[key] = new_cost
                    plan.insert_count += 1
                    session.add(
                        self._audit(
                            batch_id,
                            "FACTORY_COST_CREATED",
                            new_cost.id,
                            None,
                            _cost_snapshot(new_cost),
                        )
                    )
                    continue

                if self._same_cost(current, record):
                    plan.unchanged_count += 1
                    continue

                before = _cost_snapshot(current)
                if current.effective_from < effective_date:
                    current.effective_to = effective_date - timedelta(days=1)
                    new_cost = self._new_cost(
                        supplier=supplier,
                        batch=batch,
                        record=record,
                        effective_date=effective_date,
                    )
                    session.add(new_cost)
                    await session.flush()
                    by_key[key] = new_cost
                    changed_cost = new_cost
                elif current.effective_from == effective_date:
                    self._apply_record(current, batch, record)
                    await session.flush()
                    changed_cost = current
                else:
                    raise ValueError(
                        "Cannot import a quote effective before the current catalog version; "
                        "use a current or later --effective-date."
                    )

                plan.update_count += 1
                session.add(
                    self._audit(
                        batch_id,
                        "FACTORY_COST_UPDATED",
                        changed_cost.id,
                        before,
                        _cost_snapshot(changed_cost),
                    )
                )

            batch.status = (
                ImportStatus.COMPLETED_WITH_ERRORS
                if counts[RowStatus.ERROR]
                else ImportStatus.COMPLETED
            )
            batch.completed_at = datetime.now(UTC)
            batch.extra_data = {
                **batch.extra_data,
                "inserted": plan.insert_count,
                "updated": plan.update_count,
                "unchanged": plan.unchanged_count,
            }
            session.add(
                self._audit(
                    batch_id,
                    "FACTORY_QUOTE_IMPORT",
                    batch.id,
                    None,
                    {
                        "supplier_code": supplier.supplier_code,
                        "source_sha256": source_sha256,
                        "inserted": plan.insert_count,
                        "updated": plan.update_count,
                        "unchanged": plan.unchanged_count,
                        "warnings": counts[RowStatus.WARNING],
                        "errors": counts[RowStatus.ERROR],
                        "skipped": counts[RowStatus.SKIPPED],
                    },
                )
            )
        return plan

    @staticmethod
    async def _current_costs(session: AsyncSession, supplier_id: uuid.UUID) -> list[FactoryCost]:
        query: Select[tuple[FactoryCost]] = select(FactoryCost).where(
            FactoryCost.supplier_id == supplier_id,
            FactoryCost.effective_to.is_(None),
        )
        result = await session.execute(query)
        return list(result.scalars())

    @staticmethod
    def _same_cost(current: FactoryCost, record: NormalizedQuote) -> bool:
        return (
            current.base_product_cost == record.unit_cost
            and current.currency == record.currency
            and current.shipping_included == record.shipping_included
            and current.validation_status
            == (
                ValidationStatus.MANUAL_REVIEW
                if record.row_status is RowStatus.WARNING
                else ValidationStatus.VALID
            )
        )

    @staticmethod
    def _raw_row(
        batch: ImportBatch, supplier: Supplier, record: NormalizedQuote
    ) -> FactoryQuoteRow:
        return FactoryQuoteRow(
            import_batch_id=batch.id,
            supplier_id=supplier.id,
            source_sheet=record.source_sheet,
            source_row=record.source_row_number,
            source_column=record.source_column,
            product_type=record.product_type,
            variant_type=record.variant_type.value,
            raw_color=record.raw_color,
            raw_size=record.raw_size,
            raw_cost=record.raw_cost,
            colors_count=record.colors_count,
            size_code=record.size_code,
            width_cm=record.width_cm,
            height_cm=record.height_cm,
            unit_cost=record.unit_cost,
            currency=record.currency,
            shipping_included=record.shipping_included,
            row_status=ImportRowStatus(record.row_status.value),
            issues=[issue.model_dump(mode="json") for issue in record.issues],
            raw_payload=record.raw_payload,
        )

    @staticmethod
    def _new_cost(
        supplier: Supplier,
        batch: ImportBatch,
        record: NormalizedQuote,
        effective_date: date,
    ) -> FactoryCost:
        assert record.colors_count is not None
        assert record.width_cm is not None
        assert record.height_cm is not None
        assert record.size_code is not None
        assert record.unit_cost is not None
        return FactoryCost(
            supplier_id=supplier.id,
            import_batch_id=batch.id,
            product_type=record.product_type,
            colors_count=record.colors_count,
            source_size_label=record.raw_size or record.size_code,
            size_code=record.size_code,
            width_cm=record.width_cm,
            height_cm=record.height_cm,
            framed=record.variant_type.value == "FRAMED",
            base_product_cost=record.unit_cost,
            customization_cost=None,
            label_cost=None,
            packaging_cost=None,
            domestic_shipping_cost=None,
            other_variable_cost=None,
            total_variable_cost=None,
            currency=record.currency,
            shipping_included=record.shipping_included,
            effective_from=effective_date,
            validation_status=(
                ValidationStatus.MANUAL_REVIEW
                if record.row_status is RowStatus.WARNING
                else ValidationStatus.VALID
            ),
            cost_completeness_status=CostCompletenessStatus.INCOMPLETE,
            source_sheet=record.source_sheet,
            source_row=record.source_row_number,
            raw_payload=record.raw_payload,
        )

    @staticmethod
    def _apply_record(current: FactoryCost, batch: ImportBatch, record: NormalizedQuote) -> None:
        assert record.unit_cost is not None
        current.base_product_cost = record.unit_cost
        current.currency = record.currency
        current.shipping_included = record.shipping_included
        current.import_batch_id = batch.id
        current.source_sheet = record.source_sheet
        current.source_row = record.source_row_number
        current.source_size_label = record.raw_size or record.size_code or current.source_size_label
        current.raw_payload = record.raw_payload
        current.validation_status = (
            ValidationStatus.MANUAL_REVIEW
            if record.row_status is RowStatus.WARNING
            else ValidationStatus.VALID
        )
        current.cost_completeness_status = CostCompletenessStatus.INCOMPLETE

    @staticmethod
    def _audit(
        correlation_id: uuid.UUID,
        action: str,
        entity_id: uuid.UUID,
        before_data: dict[str, object] | None,
        after_data: dict[str, object],
    ) -> AuditLog:
        return AuditLog(
            correlation_id=correlation_id,
            actor_type="SYSTEM",
            actor_id="factory_quote_importer",
            action=action,
            entity_type="factory_cost" if "COST" in action else "import_batch",
            entity_id=entity_id,
            is_dry_run=False,
            status=AuditStatus.SUCCEEDED,
            before_data=before_data,
            after_data=after_data,
        )


def _cost_key_from_model(cost: FactoryCost) -> tuple[object, ...]:
    return (
        cost.product_type,
        cost.colors_count,
        cost.width_cm,
        cost.height_cm,
        cost.framed,
    )


def _row_counts(records: list[NormalizedQuote]) -> dict[RowStatus, int]:
    counts = {status: 0 for status in RowStatus}
    for record in records:
        counts[record.row_status] += 1
    return counts

import hashlib
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from integrations.docx.table_reader import DocxTableReader
from integrations.excel.legacy_weight_reader import LegacyWeightExcelReader
from models import PackagingRule, ProductWeightRule
from modules.fulfillment.packaging_parser import parse_packaging_tables
from modules.fulfillment.schemas import PackagingRuleRecord, ProductWeightRuleRecord
from modules.fulfillment.weight_parser import parse_weight_rows


class FulfillmentRuleService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def run(
        self,
        *,
        packaging_docx: Path,
        weight_xls: Path,
        commit: bool,
        soffice_executable: str = "soffice",
    ) -> dict[str, Any]:
        packaging_path = packaging_docx.expanduser().resolve()
        weight_path = weight_xls.expanduser().resolve()
        packaging_hash = _sha256(packaging_path)
        weight_hash = _sha256(weight_path)
        packaging_records = parse_packaging_tables(
            DocxTableReader().read(packaging_path),
            source=packaging_path.name,
            source_hash=packaging_hash,
        )
        weight_sheet = LegacyWeightExcelReader(soffice_executable).read(weight_path)
        weight_records = parse_weight_rows(
            weight_sheet.rows,
            source=weight_path.name,
            source_hash=weight_hash,
        )
        result: dict[str, Any] = {
            "packaging_rule_count": len(packaging_records),
            "weight_rule_count": len(weight_records),
            "weight_sheet": weight_sheet.name,
            "packaging_source_hash": packaging_hash,
            "weight_source_hash": weight_hash,
            "inserted": 0,
            "updated": 0,
            "unchanged": 0,
            "committed": commit,
        }
        if commit:
            async with self.session_factory() as session, session.begin():
                for packaging_record in packaging_records:
                    action = await self._upsert_packaging(session, packaging_record)
                    result[action] += 1
                for weight_record in weight_records:
                    action = await self._upsert_weight(session, weight_record)
                    result[action] += 1
        return result

    @staticmethod
    async def _upsert_packaging(session: AsyncSession, record: PackagingRuleRecord) -> str:
        statement = select(PackagingRule).where(
            PackagingRule.variant_type == record.variant_type.value,
            PackagingRule.colors_count_condition == record.colors_count_condition,
            PackagingRule.width_cm == record.width_cm,
            PackagingRule.height_cm == record.height_cm,
            PackagingRule.box_length_cm == record.box_length_cm,
            PackagingRule.box_width_cm == record.box_width_cm,
            PackagingRule.box_height_cm == record.box_height_cm,
        )
        existing = await session.scalar(statement)
        values = record.model_dump(mode="python")
        values["variant_type"] = record.variant_type.value
        if existing is None:
            session.add(PackagingRule(**values))
            return "inserted"
        changed = any(getattr(existing, key) != value for key, value in values.items())
        if not changed:
            return "unchanged"
        for key, value in values.items():
            setattr(existing, key, value)
        return "updated"

    @staticmethod
    async def _upsert_weight(session: AsyncSession, record: ProductWeightRuleRecord) -> str:
        statement = select(ProductWeightRule).where(
            ProductWeightRule.width_cm == record.width_cm,
            ProductWeightRule.height_cm == record.height_cm,
            ProductWeightRule.colors_count == record.colors_count,
            ProductWeightRule.variant_type == record.variant_type.value,
        )
        existing = await session.scalar(statement)
        values = record.model_dump(mode="python")
        values["variant_type"] = record.variant_type.value
        if existing is None:
            session.add(ProductWeightRule(**values))
            return "inserted"
        changed = any(getattr(existing, key) != value for key, value in values.items())
        if not changed:
            return "unchanged"
        for key, value in values.items():
            setattr(existing, key, value)
        return "updated"


def _sha256(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()

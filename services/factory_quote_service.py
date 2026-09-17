import hashlib
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings
from integrations.excel.factory_quote_reader import FactoryQuoteExcelReader
from integrations.excel.report_writer import FactoryQuoteReportWriter
from modules.factory_quotes.anomaly_detector import FactoryQuoteAnomalyDetector
from modules.factory_quotes.importer import FactoryQuoteImporter
from modules.factory_quotes.normalizer import FactoryQuoteNormalizer
from modules.factory_quotes.parser import FactoryQuoteParser
from modules.factory_quotes.schemas import (
    ImportMode,
    ImportResult,
    ImportSummary,
    RowStatus,
)
from modules.factory_quotes.validator import FactoryQuoteValidator

SessionFactory = Callable[[], AsyncSession]


def sha256_file(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class FactoryQuoteService:
    def __init__(
        self,
        settings: Settings,
        session_factory: SessionFactory,
        report_writer: FactoryQuoteReportWriter | None = None,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.report_writer = report_writer or FactoryQuoteReportWriter(settings)
        self.reader = FactoryQuoteExcelReader()
        self.parser = FactoryQuoteParser()
        self.importer = FactoryQuoteImporter()

    async def run(
        self,
        *,
        file_path: Path,
        supplier_code: str,
        mode: ImportMode,
        sheet_name: str | None = None,
        force: bool = False,
        output_dir: Path = Path("outputs/imports"),
        effective_date: date | None = None,
    ) -> ImportResult:
        started_at = datetime.now(UTC)
        path = file_path.expanduser().resolve()
        supplier_code = supplier_code.upper()
        profile = self.settings.supplier_profile(supplier_code)
        worksheet = self.reader.read(path, sheet_name)
        candidates = self.parser.parse(worksheet)

        normalizer = FactoryQuoteNormalizer(
            supplier_code=supplier_code,
            currency=profile.currency,
            product_type=self.settings.factory_quotes.product_type,
            unavailable_markers=self.settings.imports.unavailable_markers,
        )
        validator = FactoryQuoteValidator(self.settings.factory_quotes.allowed_color_counts)
        records = [validator.validate(normalizer.normalize(candidate)) for candidate in candidates]
        detector = FactoryQuoteAnomalyDetector(
            suspicious_low_ratio=self.settings.factory_quotes.suspicious_low_ratio,
            size_inversion_ratio=self.settings.factory_quotes.size_inversion_ratio,
            color_inversion_ratio=self.settings.factory_quotes.color_inversion_ratio,
        )
        detector.detect(records)

        source_hash = sha256_file(path)
        batch_id = uuid.uuid4()
        async with self.session_factory() as session:
            plan = await self.importer.plan(
                session,
                supplier_code=supplier_code,
                source_sha256=source_hash,
                records=records,
                force=force,
            )

        status_counts = {status: 0 for status in RowStatus}
        for record in records:
            status_counts[record.row_status] += 1
        summary = ImportSummary(
            parsed_count=len(records),
            valid_count=status_counts[RowStatus.VALID],
            warning_count=status_counts[RowStatus.WARNING],
            error_count=status_counts[RowStatus.ERROR],
            skipped_count=status_counts[RowStatus.SKIPPED],
            issue_count=sum(len(record.issues) for record in records),
        )
        result = ImportResult(
            batch_id=batch_id,
            mode=mode,
            supplier_code=supplier_code,
            source_file=path,
            source_sha256=source_hash,
            source_sheet=worksheet.name,
            effective_date=effective_date or date.today(),
            started_at=started_at,
            completed_at=datetime.now(UTC),
            summary=summary,
            plan=plan,
            records=records,
            committed=False,
        )

        report_path = output_dir.resolve() / str(batch_id) / "factory_quote_validation.xlsx"
        result.report_path = report_path

        if mode is ImportMode.COMMIT:
            async with self.session_factory() as session:
                result.plan = await self.importer.commit(
                    session,
                    batch_id=batch_id,
                    supplier_code=supplier_code,
                    supplier_profile=profile,
                    source_filename=path.name,
                    source_sha256=source_hash,
                    source_sheet=worksheet.name,
                    effective_date=result.effective_date,
                    records=records,
                    force=force,
                    report_path=str(report_path),
                    started_at=started_at,
                )
            result.committed = True
            result.completed_at = datetime.now(UTC)

        self.report_writer.write(result, report_path)
        return result

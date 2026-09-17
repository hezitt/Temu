import argparse
import asyncio
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy.exc import SQLAlchemyError

from core.config import get_settings
from core.database import async_session_factory, dispose_engine
from core.logging import configure_logging
from integrations.excel.factory_quote_reader import FactoryQuoteReadError
from integrations.excel.report_writer import FactoryQuoteReportError
from modules.factory_quotes.parser import FactoryQuoteLayoutError
from modules.factory_quotes.schemas import DuplicateFileError, ImportMode, IssueCode
from services.factory_quote_service import FactoryQuoteService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and import a supplier factory quote workbook."
    )
    parser.add_argument("--file", required=True, type=Path, help="Path to the supplier .xlsx file")
    parser.add_argument("--supplier", required=True, help="Configured supplier code")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Preview only; this is the default")
    mode.add_argument("--commit", action="store_true", help="Write import data to PostgreSQL")
    parser.add_argument("--sheet", help="Worksheet name; defaults to the first worksheet")
    parser.add_argument("--force", action="store_true", help="Reprocess an already imported file")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/imports"),
        help="Validation report root directory",
    )
    parser.add_argument(
        "--effective-date",
        type=date.fromisoformat,
        help="Catalog effective date in YYYY-MM-DD format; defaults to today",
    )
    return parser.parse_args()


def print_result(result: object) -> None:
    from modules.factory_quotes.schemas import ImportResult

    assert isinstance(result, ImportResult)
    no_quote_count = sum(
        1
        for record in result.records
        if any(issue.issue_code is IssueCode.NO_QUOTE for issue in record.issues)
    )
    separator_count = sum(
        1
        for record in result.records
        if any(issue.issue_code is IssueCode.SEPARATOR_ROW for issue in record.issues)
    )
    skipped_total = (
        result.summary.skipped_count + result.summary.error_count + result.plan.unchanged_count
    )
    title = (
        "Factory Quote Import Complete"
        if result.mode is ImportMode.COMMIT
        else "Factory Quote Import Preview"
    )
    print(title)
    print(f"Supplier: {result.supplier_code}")
    print(f"File: {result.source_file.name}")
    print(f"Sheet: {result.source_sheet}")
    print(f"Batch: {result.batch_id}")
    print(f"Parsed candidates: {result.summary.parsed_count}")
    print(f"Valid: {result.summary.valid_count}")
    print(f"Warning rows: {result.summary.warning_count}")
    print(f"Error rows: {result.summary.error_count}")
    print(f"No quote: {no_quote_count}")
    print(f"Separator candidates: {separator_count}")
    verb = "Inserted" if result.mode is ImportMode.COMMIT else "Would insert"
    print(f"{verb}: {result.plan.insert_count}")
    verb = "Updated" if result.mode is ImportMode.COMMIT else "Would update"
    print(f"{verb}: {result.plan.update_count}")
    verb = "Skipped" if result.mode is ImportMode.COMMIT else "Would skip"
    print(f"{verb}: {skipped_total}")
    print(f"Validation report: {result.report_path}")
    if result.mode is ImportMode.DRY_RUN:
        print("Database changes NOT committed.")


async def run() -> int:
    args = parse_args()
    configure_logging()
    settings = get_settings()
    service = FactoryQuoteService(settings, async_session_factory)
    mode = ImportMode.COMMIT if args.commit else ImportMode.DRY_RUN
    try:
        result = await service.run(
            file_path=args.file,
            supplier_code=args.supplier,
            mode=mode,
            sheet_name=args.sheet,
            force=args.force,
            output_dir=args.output_dir,
            effective_date=args.effective_date,
        )
    except DuplicateFileError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except (
        FactoryQuoteReadError,
        FactoryQuoteLayoutError,
        FactoryQuoteReportError,
        SQLAlchemyError,
        ValueError,
    ) as exc:
        print(f"Factory quote import failed: {exc}", file=sys.stderr)
        return 4
    finally:
        await dispose_engine()

    print_result(result)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))

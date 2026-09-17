import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.database import async_session_factory, dispose_engine
from integrations.docx.table_reader import DocxTableReadError
from integrations.excel.legacy_weight_reader import LegacyWeightReadError
from modules.fulfillment.packaging_parser import PackagingTableError
from modules.fulfillment.weight_parser import WeightTableError
from services.fulfillment_rule_service import FulfillmentRuleService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and import factory packaging and product weight rules."
    )
    parser.add_argument("--packaging-docx", required=True, type=Path)
    parser.add_argument("--weight-xls", required=True, type=Path)
    parser.add_argument("--soffice", default="soffice")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--commit", action="store_true")
    return parser.parse_args()


async def run() -> int:
    args = parse_args()
    try:
        result = await FulfillmentRuleService(async_session_factory).run(
            packaging_docx=args.packaging_docx,
            weight_xls=args.weight_xls,
            commit=args.commit,
            soffice_executable=args.soffice,
        )
    except (
        DocxTableReadError,
        LegacyWeightReadError,
        PackagingTableError,
        WeightTableError,
        OSError,
        ValueError,
    ) as exc:
        print(f"Fulfillment rule import failed: {exc}", file=sys.stderr)
        return 4
    finally:
        await dispose_engine()
    print("Fulfillment Rule Import" if args.commit else "Fulfillment Rule Preview")
    print(f"Packaging rules: {result['packaging_rule_count']}")
    print(f"Weight rules: {result['weight_rule_count']}")
    print(f"Inserted: {result['inserted']}")
    print(f"Updated: {result['updated']}")
    print(f"Unchanged: {result['unchanged']}")
    if not args.commit:
        print("Database changes NOT committed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))

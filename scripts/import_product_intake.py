import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config import get_settings
from core.database import async_session_factory, dispose_engine
from services.product_intake_service import ProductIntakeError, ProductIntakeService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and import product, design, and SKU master data from an intake JSON."
    )
    parser.add_argument("--intake", required=True, type=Path)
    parser.add_argument("--supplier", default="LINGDIAN")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--commit", action="store_true")
    return parser.parse_args()


async def run() -> int:
    args = parse_args()
    try:
        result = await ProductIntakeService(get_settings(), async_session_factory).run(
            intake_path=args.intake,
            supplier_code=args.supplier,
            commit=args.commit,
        )
    except (OSError, ProductIntakeError, ValueError) as exc:
        print(f"Product intake import failed: {exc}", file=sys.stderr)
        return 4
    finally:
        await dispose_engine()

    print("Product Intake Import" if args.commit else "Product Intake Preview")
    print(f"Design: {result['design_code']}")
    print(f"Internal SPU: {result['product_code']}")
    print(f"SKUs: {result['sku_count']}")
    print(f"Inserted: {result['inserted']}")
    print(f"Updated: {result['updated']}")
    print(f"Unchanged: {result['unchanged']}")
    if not args.commit:
        print("Database changes NOT committed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))

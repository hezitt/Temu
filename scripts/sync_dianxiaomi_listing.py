import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.database import async_session_factory, dispose_engine
from modules.listing.external_ids import load_dianxiaomi_listing_observation
from services.listing_external_id_service import (
    ListingExternalIdService,
    ListingExternalIdSyncError,
)


def _iso_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "must be an ISO 8601 timestamp, for example 2026-09-20T10:30:00+08:00"
        ) from exc
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("timestamp must include a UTC offset")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and sync store-scoped SPU/SKC/SKU IDs observed in Dianxiaomi. "
            "The command previews changes unless --commit is supplied."
        )
    )
    parser.add_argument("--intake", required=True, type=Path)
    parser.add_argument("--supplier", default="LINGDIAN")
    parser.add_argument("--store-code", required=True)
    parser.add_argument("--observed-at", type=_iso_datetime)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--commit", action="store_true")
    return parser.parse_args()


async def run() -> int:
    args = parse_args()
    try:
        observation = load_dianxiaomi_listing_observation(
            args.intake,
            observed_at=args.observed_at,
        )
        result = await ListingExternalIdService(async_session_factory).run(
            observation=observation,
            supplier_code=args.supplier,
            store_code=args.store_code,
            commit=args.commit,
        )
    except (FileNotFoundError, ListingExternalIdSyncError, OSError, ValueError) as exc:
        print(f"Dianxiaomi listing ID sync failed: {exc}", file=sys.stderr)
        return 4
    finally:
        await dispose_engine()

    print("Dianxiaomi Listing ID Sync" if args.commit else "Dianxiaomi Listing ID Preview")
    print(f"Internal SPU: {result['internal_spu_item_code']}")
    print(f"Dianxiaomi SPU ID: {result['dianxiaomi_spu_id']}")
    print(f"Temu SKC ID: {result['temu_skc_id']}")
    print(f"SKUs checked: {result['sku_count']}")
    print(f"Inserted: {result['inserted']}")
    print(f"Updated: {result['updated']}")
    print(f"Unchanged: {result['unchanged']}")
    if result["seller_center_confirmation_pending"]:
        print("Temu Seller Center ID confirmation is still pending.")
    if not args.commit:
        print("Database changes NOT committed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))

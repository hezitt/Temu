import argparse
import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config import get_settings
from core.database import async_session_factory, dispose_engine
from integrations.fangguo.client import FangguoClient, FangguoClientError
from services.fangguo_order_sync_service import FangguoOrderSyncError, FangguoOrderSyncService


def _iso_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("timestamp must include a UTC offset")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read Temu US semi-managed order IDs and details from Fangguo."
    )
    parser.add_argument("--store-code", default="US_MAIN")
    parser.add_argument("--connection-name", default="merchant-api")
    parser.add_argument("--start", type=_iso_datetime)
    parser.add_argument("--end", type=_iso_datetime)
    parser.add_argument("--factory-id", type=int)
    parser.add_argument("--shop-id", type=int)
    parser.add_argument("--order-status", type=int, choices=range(0, 6))
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--commit", action="store_true")
    return parser.parse_args()


async def run() -> int:
    args = parse_args()
    settings = get_settings()
    end_time = args.end or datetime.now(UTC)
    start_time = args.start or end_time - timedelta(
        minutes=settings.fangguo.rolling_lookback_minutes
    )
    try:
        async with FangguoClient(settings.fangguo) as client:
            result = await FangguoOrderSyncService(
                async_session_factory,
                client,
                platform_type=settings.fangguo.platform_type,
                page_size=settings.fangguo.page_size,
                rolling_lookback_minutes=settings.fangguo.rolling_lookback_minutes,
            ).run(
                store_code=args.store_code,
                connection_name=args.connection_name,
                start_time=start_time,
                end_time=end_time,
                factory_id=args.factory_id,
                shop_id=args.shop_id,
                order_status=args.order_status,
                commit=args.commit,
            )
    except (FangguoClientError, FangguoOrderSyncError, ValueError) as exc:
        print(f"Fangguo order sync failed: {exc}", file=sys.stderr)
        return 4
    finally:
        await dispose_engine()

    print("Fangguo Order Sync" if args.commit else "Fangguo Order Sync Preview")
    print(f"Payment window: {result['window_start']} -> {result['window_end']}")
    print(f"Orders read: {result['orders_read']}")
    print(f"Items read: {result['items_read']}")
    print(f"Orders inserted: {result['inserted_orders']}")
    print(f"Orders updated: {result['updated_orders']}")
    print(f"Items matched: {result['matched_items']}")
    print(f"Items requiring review: {result['review_items']}")
    if not args.commit:
        print("Database changes NOT committed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))

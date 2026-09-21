import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from core.config import get_settings
from integrations.sorftime.client import SorftimeClient
from integrations.sorftime.schemas import (
    CategoryRequest,
    CategorySearchFromNameRequest,
    ProductRequest,
    ProductSearchFromNameRequest,
    ProductSearchRequest,
    ProductTrendRequest,
    SorftimeModel,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan or execute a budget-protected Sorftime Temu API request."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Send the request. Without this flag, only a zero-cost plan is printed.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("category-tree")

    category_search = subparsers.add_parser("category-search")
    category_search.add_argument("--name", required=True)

    category = subparsers.add_parser("category")
    category.add_argument("--node-id", required=True)

    product = subparsers.add_parser("product")
    product.add_argument("--product-id", required=True)

    product_trend = subparsers.add_parser("product-trend")
    product_trend.add_argument("--product-id", required=True)

    product_name_search = subparsers.add_parser("product-name-search")
    product_name_search.add_argument("--name", required=True)
    product_name_search.add_argument("--page", type=int, default=1)

    product_search = subparsers.add_parser("product-search")
    product_search.add_argument(
        "--request-file",
        type=Path,
        required=True,
        help="JSON object containing ProductSearch request fields from the Sorftime docs.",
    )
    return parser


def build_request(args: argparse.Namespace) -> tuple[str, SorftimeModel]:
    if args.command == "category-tree":
        return "CategoryTree", SorftimeModel()
    if args.command == "category-search":
        return "CategorySearchFromName", CategorySearchFromNameRequest(name=args.name)
    if args.command == "category":
        return "CategoryRequest", CategoryRequest(node_id=args.node_id)
    if args.command == "product":
        return "ProductRequest", ProductRequest(product_id=args.product_id)
    if args.command == "product-trend":
        return "ProductTrendRequest", ProductTrendRequest(product_id=args.product_id)
    if args.command == "product-name-search":
        return (
            "ProductSearchFromName",
            ProductSearchFromNameRequest(name=args.name, page=args.page),
        )
    if args.command == "product-search":
        raw = json.loads(args.request_file.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("ProductSearch request file must contain one JSON object")
        return "ProductSearch", ProductSearchRequest.model_validate(raw)
    raise ValueError(f"Unsupported command: {args.command}")


async def execute(args: argparse.Namespace) -> int:
    settings = get_settings()
    endpoint, request = build_request(args)
    async with SorftimeClient(settings.sorftime) as client:
        plan = client.plan(endpoint, request)
        response_path = settings.sorftime.cache_dir / "responses" / f"{plan.cache_key}.json"
        output: dict[str, Any] = {
            "mode": "execute" if args.execute else "plan",
            "endpoint": plan.endpoint,
            "domain": plan.domain,
            "body": plan.body,
            "request_cost": plan.cost,
            "estimated_remaining_before": client.estimated_remaining_budget(),
            "cache_path": str(response_path),
            "cached": response_path.exists(),
        }
        if not args.execute:
            print(json.dumps(output, ensure_ascii=False, indent=2))
            return 0

        response = await _dispatch(client, args, request)
        output.update(
            {
                "request_consumed": response.request_consumed,
                "server_request_left": response.request_left,
                "code": response.code,
                "message": response.message,
                "estimated_remaining_after": client.estimated_remaining_budget(),
            }
        )
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0


async def _dispatch(
    client: SorftimeClient,
    args: argparse.Namespace,
    request: SorftimeModel,
) -> Any:
    if args.command == "category-tree":
        return await client.get_category_tree()
    if args.command == "category-search":
        return await client.search_categories(args.name)
    if args.command == "category":
        return await client.get_category(args.node_id)
    if args.command == "product":
        return await client.get_product(args.product_id)
    if args.command == "product-trend":
        return await client.get_product_trend(args.product_id)
    if args.command == "product-name-search":
        return await client.search_products_by_name(args.name, page=args.page)
    if args.command == "product-search":
        if not isinstance(request, ProductSearchRequest):
            raise TypeError("Expected a ProductSearchRequest")
        return await client.search_products(request)
    raise ValueError(f"Unsupported command: {args.command}")


def main() -> int:
    args = build_parser().parse_args()
    return asyncio.run(execute(args))


if __name__ == "__main__":
    raise SystemExit(main())

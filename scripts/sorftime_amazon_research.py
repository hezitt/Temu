import argparse
import asyncio
import json
from datetime import date
from pathlib import Path
from typing import Any

from core.config import get_settings
from integrations.sorftime.amazon import SorftimeAmazonClient
from integrations.sorftime.amazon_schemas import (
    AmazonCategoryProductsRequest,
    AmazonCategoryRequest,
    AmazonCategoryTrendRequest,
    AmazonKeywordRequest,
    AmazonKeywordSearchResultsRequest,
    AmazonProductCustomersSayRequest,
    AmazonProductRequest,
    AmazonProductSearchFromNameRequest,
    AmazonProductSearchRequest,
    AmazonSimilarProductFeatureRequest,
)
from integrations.sorftime.schemas import CategorySearchFromNameRequest, SorftimeModel


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan or execute a budget-protected Sorftime Amazon US API request."
    )
    parser.add_argument("--execute", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)

    category_search = commands.add_parser("category-search")
    category_search.add_argument("--name", required=True)

    category = commands.add_parser("category")
    category.add_argument("--node-id", required=True)
    category.add_argument("--query-start", type=date.fromisoformat)
    category.add_argument("--query-date", type=date.fromisoformat)
    category.add_argument("--query-days", type=int)

    category_products = commands.add_parser("category-products")
    category_products.add_argument("--node-id", required=True)
    category_products.add_argument("--page", type=int, default=1)

    category_trend = commands.add_parser("category-trend")
    category_trend.add_argument("--node-id", required=True)
    category_trend.add_argument("--trend-index", type=int, required=True)

    product = commands.add_parser("product")
    product.add_argument(
        "--asin",
        required=True,
        help="One ASIN or up to ten comma-separated ASINs",
    )
    product.add_argument("--trend", type=int, choices=(1, 2), default=1)
    product.add_argument("--trend-start", type=date.fromisoformat)
    product.add_argument("--trend-end", type=date.fromisoformat)

    product_name = commands.add_parser("product-name-search")
    product_name.add_argument("--name", required=True)
    product_name.add_argument("--page", type=int, default=1)

    product_search = commands.add_parser("product-search")
    product_search.add_argument("--request-file", type=Path, required=True)

    customers_say = commands.add_parser("customers-say")
    customers_say.add_argument("--asin", required=True)

    similar_features = commands.add_parser("similar-features")
    similar_features.add_argument("--product-name", required=True)

    keyword = commands.add_parser("keyword")
    keyword.add_argument("--keyword", required=True)

    keyword_products = commands.add_parser("keyword-products")
    keyword_products.add_argument("--keyword", required=True)
    keyword_products.add_argument("--position-type", type=int, choices=(0, 1, 2), default=1)
    keyword_products.add_argument("--page", type=int, default=1)
    keyword_products.add_argument("--page-size", type=int, default=20)
    return parser


def build_request(args: argparse.Namespace) -> tuple[str, SorftimeModel]:
    if args.command == "category-search":
        return "CategorySearchFromName", CategorySearchFromNameRequest(name=args.name)
    if args.command == "category":
        return (
            "CategoryRequest",
            AmazonCategoryRequest(
                node_id=args.node_id,
                query_start=args.query_start,
                query_date=args.query_date,
                query_days=args.query_days,
            ),
        )
    if args.command == "category-products":
        return (
            "CategoryProducts",
            AmazonCategoryProductsRequest(node_id=args.node_id, page=args.page),
        )
    if args.command == "category-trend":
        return (
            "CategoryTrend",
            AmazonCategoryTrendRequest(
                node_id=args.node_id,
                trend_index=args.trend_index,
            ),
        )
    if args.command == "product":
        return (
            "ProductRequest",
            AmazonProductRequest(
                asin=args.asin,
                trend=args.trend,
                query_trend_start=args.trend_start,
                query_trend_end=args.trend_end,
            ),
        )
    if args.command == "product-name-search":
        return (
            "ProductSearchFromName",
            AmazonProductSearchFromNameRequest(name=args.name, page_index=args.page),
        )
    if args.command == "product-search":
        raw = json.loads(args.request_file.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Amazon ProductSearch request file must contain one JSON object")
        return "ProductSearch", AmazonProductSearchRequest.model_validate(raw)
    if args.command == "customers-say":
        return "ProductCustomersSay", AmazonProductCustomersSayRequest(asin=args.asin)
    if args.command == "similar-features":
        return (
            "SimilarProductFeature",
            AmazonSimilarProductFeatureRequest(product_name=args.product_name),
        )
    if args.command == "keyword":
        return "KeywordRequest", AmazonKeywordRequest(keyword=args.keyword)
    if args.command == "keyword-products":
        return (
            "KeywordSearchResults",
            AmazonKeywordSearchResultsRequest(
                keyword=args.keyword,
                position_type=args.position_type,
                page_index=args.page,
                page_size=args.page_size,
            ),
        )
    raise ValueError(f"Unsupported command: {args.command}")


async def execute(args: argparse.Namespace) -> int:
    settings = get_settings()
    endpoint, request = build_request(args)
    async with SorftimeAmazonClient(settings.sorftime) as client:
        plan = client.plan(endpoint, request)
        response_path = settings.sorftime.cache_dir / "responses" / f"{plan.cache_key}.json"
        output: dict[str, Any] = {
            "mode": "execute" if args.execute else "plan",
            "marketplace": "amazon",
            "endpoint": plan.endpoint,
            "domain": plan.domain,
            "body": plan.body,
            "request_cost": plan.cost,
            "estimated_remaining_before": client.estimated_remaining_budget(),
            "cache_path": str(response_path),
            "cached": response_path.exists(),
        }
        if not args.execute:
            print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
            return 0

        response = await dispatch(client, endpoint, request)
        output.update(
            {
                "request_consumed": response.request_consumed,
                "server_request_left": response.request_left,
                "code": response.code,
                "message": response.message,
                "estimated_remaining_after": client.estimated_remaining_budget(),
            }
        )
        print(json.dumps(output, ensure_ascii=False, indent=2, default=str))
        return 0


async def dispatch(
    client: SorftimeAmazonClient,
    endpoint: str,
    request: SorftimeModel,
) -> Any:
    if endpoint == "CategorySearchFromName":
        assert isinstance(request, CategorySearchFromNameRequest)
        return await client.search_categories(request.name)
    if endpoint == "CategoryRequest":
        assert isinstance(request, AmazonCategoryRequest)
        return await client.get_category(request)
    if endpoint == "CategoryProducts":
        assert isinstance(request, AmazonCategoryProductsRequest)
        return await client.get_category_products(request)
    if endpoint == "CategoryTrend":
        assert isinstance(request, AmazonCategoryTrendRequest)
        return await client.get_category_trend(request)
    if endpoint == "ProductRequest":
        assert isinstance(request, AmazonProductRequest)
        return await client.get_product(request)
    if endpoint == "ProductSearchFromName":
        assert isinstance(request, AmazonProductSearchFromNameRequest)
        return await client.search_products_by_name(request)
    if endpoint == "ProductSearch":
        assert isinstance(request, AmazonProductSearchRequest)
        return await client.search_products(request)
    if endpoint == "ProductCustomersSay":
        assert isinstance(request, AmazonProductCustomersSayRequest)
        return await client.get_customers_say(request)
    if endpoint == "SimilarProductFeature":
        assert isinstance(request, AmazonSimilarProductFeatureRequest)
        return await client.get_similar_features(request)
    if endpoint == "KeywordRequest":
        assert isinstance(request, AmazonKeywordRequest)
        return await client.get_keyword(request)
    if endpoint == "KeywordSearchResults":
        assert isinstance(request, AmazonKeywordSearchResultsRequest)
        return await client.get_keyword_products(request)
    raise ValueError(f"Unsupported endpoint: {endpoint}")


def main() -> int:
    return asyncio.run(execute(build_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())

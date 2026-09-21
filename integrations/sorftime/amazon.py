import math
from datetime import date

import httpx
from pydantic import SecretStr

from core.config import SorftimeSettings
from integrations.sorftime.amazon_schemas import (
    AmazonAsinSalesVolumeRequest,
    AmazonCategoryKeywordsRequest,
    AmazonCategoryProductsRequest,
    AmazonCategoryRequest,
    AmazonCategoryTrendRequest,
    AmazonKeywordRequest,
    AmazonKeywordSearchResultsRequest,
    AmazonProductCustomersSayRequest,
    AmazonProductRequest,
    AmazonProductSearchFromNameRequest,
    AmazonProductSearchRequest,
    AmazonProductVariationsRequest,
    AmazonSimilarProductFeatureRequest,
)
from integrations.sorftime.client import SorftimeClient
from integrations.sorftime.schemas import (
    CategorySearchFromNameRequest,
    RequestPlan,
    SorftimeEnvelope,
    SorftimeModel,
)


class SorftimeAmazonClient:
    """Amazon US selection-data adapter sharing Sorftime cache and request ledger."""

    DOMAIN_US = 1
    FIXED_COSTS = {
        "CategorySearchFromName": 1,
        "CategoryProducts": 5,
        "CategoryTrend": 5,
        "ProductSearchFromName": 2,
        "ProductSearch": 5,
        "AsinSalesVolume": 1,
        "ProductCustomersSay": 1,
        "SimilarProductFeature": 2,
        "KeywordRequest": 1,
        "KeywordSearchResults": 5,
        "CategoryRequestKeyword": 1,
    }

    def __init__(
        self,
        settings: SorftimeSettings,
        *,
        account_sk: SecretStr | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._client = SorftimeClient(
            settings,
            domain=self.DOMAIN_US,
            account_sk=account_sk,
            http_client=http_client,
        )

    async def __aenter__(self) -> "SorftimeAmazonClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.close()

    def estimated_remaining_budget(self) -> int:
        return self._client.estimated_remaining_budget()

    def plan(self, endpoint: str, request: SorftimeModel) -> RequestPlan:
        return self._client.plan(
            endpoint,
            request,
            cost_override=self.request_cost(endpoint, request),
        )

    def request_cost(self, endpoint: str, request: SorftimeModel) -> int:
        if endpoint == "CategoryRequest":
            if not isinstance(request, AmazonCategoryRequest):
                raise TypeError("CategoryRequest requires AmazonCategoryRequest")
            return _category_request_cost(request)
        if endpoint == "ProductRequest":
            if not isinstance(request, AmazonProductRequest):
                raise TypeError("ProductRequest requires AmazonProductRequest")
            return _product_request_cost(request)
        if endpoint == "ProductVariations":
            if not isinstance(request, AmazonProductVariationsRequest):
                raise TypeError("ProductVariations requires AmazonProductVariationsRequest")
            return 2 if request.include_sales_volume else 1
        if endpoint == "CategoryTree":
            return 5
        try:
            return self.FIXED_COSTS[endpoint]
        except KeyError as exc:
            raise ValueError(f"Unsupported Sorftime Amazon endpoint: {endpoint}") from exc

    async def _request(self, endpoint: str, request: SorftimeModel) -> SorftimeEnvelope:
        return await self._client.request_endpoint(
            endpoint,
            request,
            cost_override=self.request_cost(endpoint, request),
        )

    async def get_category_tree(self) -> SorftimeEnvelope:
        return await self._request("CategoryTree", SorftimeModel())

    async def search_categories(self, name: str) -> SorftimeEnvelope:
        return await self._request(
            "CategorySearchFromName",
            CategorySearchFromNameRequest(name=name),
        )

    async def get_category(self, request: AmazonCategoryRequest) -> SorftimeEnvelope:
        return await self._request("CategoryRequest", request)

    async def get_category_products(
        self, request: AmazonCategoryProductsRequest
    ) -> SorftimeEnvelope:
        return await self._request("CategoryProducts", request)

    async def get_category_trend(
        self, request: AmazonCategoryTrendRequest
    ) -> SorftimeEnvelope:
        return await self._request("CategoryTrend", request)

    async def get_product(self, request: AmazonProductRequest) -> SorftimeEnvelope:
        return await self._request("ProductRequest", request)

    async def search_products_by_name(
        self, request: AmazonProductSearchFromNameRequest
    ) -> SorftimeEnvelope:
        return await self._request("ProductSearchFromName", request)

    async def search_products(self, request: AmazonProductSearchRequest) -> SorftimeEnvelope:
        return await self._request("ProductSearch", request)

    async def get_sales_volume(
        self, request: AmazonAsinSalesVolumeRequest
    ) -> SorftimeEnvelope:
        return await self._request("AsinSalesVolume", request)

    async def get_variations(
        self, request: AmazonProductVariationsRequest
    ) -> SorftimeEnvelope:
        return await self._request("ProductVariations", request)

    async def get_customers_say(
        self, request: AmazonProductCustomersSayRequest
    ) -> SorftimeEnvelope:
        return await self._request("ProductCustomersSay", request)

    async def get_similar_features(
        self, request: AmazonSimilarProductFeatureRequest
    ) -> SorftimeEnvelope:
        return await self._request("SimilarProductFeature", request)

    async def get_keyword(self, request: AmazonKeywordRequest) -> SorftimeEnvelope:
        return await self._request("KeywordRequest", request)

    async def get_keyword_products(
        self, request: AmazonKeywordSearchResultsRequest
    ) -> SorftimeEnvelope:
        return await self._request("KeywordSearchResults", request)

    async def get_category_keywords(
        self, request: AmazonCategoryKeywordsRequest
    ) -> SorftimeEnvelope:
        return await self._request("CategoryRequestKeyword", request)


def _category_request_cost(request: AmazonCategoryRequest) -> int:
    if request.query_start is None and request.query_days is None:
        return 5
    if request.query_days is not None:
        days = request.query_days
    else:
        assert request.query_start is not None
        assert request.query_date is not None
        days = (request.query_date - request.query_start).days + 1
    if not 3 <= days <= 40:
        raise ValueError("Amazon historical category range must span 3 to 40 days")
    return math.ceil(days / 3) * 10


def _product_request_cost(request: AmazonProductRequest) -> int:
    multiplier = 1
    if request.query_trend_start is not None:
        end = request.query_trend_end or date.today()
        if (end - request.query_trend_start).days + 1 > 15:
            multiplier = 2
    return len(request.asins) * multiplier

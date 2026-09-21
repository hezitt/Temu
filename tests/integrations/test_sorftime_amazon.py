import base64
import gzip
import json
from datetime import date
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from core.config import SorftimeSettings
from integrations.sorftime.amazon import SorftimeAmazonClient
from integrations.sorftime.amazon_schemas import (
    AmazonCategoryRequest,
    AmazonProductRequest,
    AmazonProductVariationsRequest,
)


def _encoded(payload: dict[str, object]) -> bytes:
    return base64.b64encode(gzip.compress(json.dumps(payload).encode("utf-8")))


def test_amazon_dynamic_request_costs(tmp_path: Path) -> None:
    client = SorftimeAmazonClient(SorftimeSettings(cache_dir=tmp_path))

    realtime_category = AmazonCategoryRequest(node_id="2617941011")
    four_day_history = AmazonCategoryRequest(
        node_id="2617941011",
        query_start=date(2026, 9, 1),
        query_date=date(2026, 9, 4),
    )
    ten_asins = AmazonProductRequest(
        asin=",".join(f"B0000000{i:02d}" for i in range(10)),
        trend=2,
    )
    long_trend = AmazonProductRequest(
        asin="B000000001",
        trend=1,
        query_trend_start=date(2026, 8, 1),
        query_trend_end=date(2026, 9, 1),
    )

    assert client.request_cost("CategoryRequest", realtime_category) == 5
    assert client.request_cost("CategoryRequest", four_day_history) == 20
    assert client.request_cost("ProductRequest", ten_asins) == 10
    assert client.request_cost("ProductRequest", long_trend) == 2
    assert (
        client.request_cost(
            "ProductVariations",
            AmazonProductVariationsRequest(
                asin="B000000001",
                include_sales_volume=True,
            ),
        )
        == 2
    )


@pytest.mark.asyncio
async def test_amazon_category_search_uses_us_domain_and_shared_ledger(tmp_path: Path) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["domain"] == "1"
        assert request.headers["Authorization"] == "BasicAuth amazon-test-sk"
        assert json.loads(request.content) == {"Name": "paint by numbers"}
        return httpx.Response(
            200,
            content=_encoded(
                {
                    "RequestLeft": 28,
                    "RequestConsumed": 1,
                    "Code": 0,
                    "Message": None,
                    "Data": [
                        {
                            "NodeId": "2617941011",
                            "CategoryName": "Adults' Paint-By-Number Kits",
                        }
                    ],
                }
            ),
        )

    http_client = httpx.AsyncClient(
        base_url="https://standardapi.sorftime.test/api",
        transport=httpx.MockTransport(handler),
    )
    client = SorftimeAmazonClient(
        SorftimeSettings(
            live_requests_enabled=True,
            request_budget=50,
            cache_dir=tmp_path,
        ),
        account_sk=SecretStr("amazon-test-sk"),
        http_client=http_client,
    )
    response = await client.search_categories("paint by numbers")
    assert response.request_left == 28
    ledger = json.loads((tmp_path / "request-ledger.jsonl").read_text(encoding="utf-8"))
    assert ledger["domain"] == 1
    assert ledger["request_consumed"] == 1
    await client.close()


def test_amazon_product_request_limits_asin_count() -> None:
    with pytest.raises(ValueError):
        AmazonProductRequest(
            asin=",".join(f"B0000000{i:02d}" for i in range(11)),
            trend=2,
        )

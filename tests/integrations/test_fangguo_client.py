import json

import httpx
import pytest
from pydantic import SecretStr

from core.config import FangguoSettings
from integrations.fangguo.client import (
    FangguoClient,
    FangguoConfigurationError,
    FangguoResponseError,
)
from integrations.fangguo.schemas import FangguoTidListRequest


def _client(handler: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url="https://open.fangguo.test/fgapp/openapi",
        transport=handler,
    )


@pytest.mark.asyncio
async def test_lists_stores_with_bearer_authentication() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        assert request.url.path.endswith("/shop/store/list")
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "list": [
                        {
                            "id": 24,
                            "platform": 25,
                            "authId": "masked",
                            "nick": "US Main",
                            "brandName": "Temu",
                            "defaultFactory": 3000046,
                            "autoSync": True,
                        }
                    ]
                },
                "msg": "",
            },
        )

    http_client = _client(httpx.MockTransport(handler))
    client = FangguoClient(
        FangguoSettings(),
        api_key=SecretStr("test-key"),
        http_client=http_client,
    )
    stores = await client.list_stores()
    assert stores[0].id == 24
    assert stores[0].default_factory == 3000046
    await http_client.aclose()


@pytest.mark.asyncio
async def test_lists_us_semi_managed_tids_and_parses_order_detail() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/order/tidList"):
            body = json.loads(request.content)
            assert body["platformType"] == 225
            assert body["pageSize"] == 100
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {"list": [{"tid": "T-1"}], "total": 1, "cursor": None},
                    "msg": "",
                },
            )
        assert request.url.path.endswith("/order/detail")
        assert request.url.params["tid"] == "T-1"
        return httpx.Response(
            200,
            json={
                "code": 0,
                "data": {
                    "orderType": 0,
                    "id": "record-1",
                    "factoryId": 3000046,
                    "sysTid": "SYS-1",
                    "tid": "T-1",
                    "platform": 225,
                    "dfStatus": 4,
                    "outerOrderStatusDesc": "待发货",
                    "platformDesc": "Temu(半托管-美区)",
                    "storeName": "US Main",
                    "orderItems": [
                        {
                            "id": "item-1",
                            "oid": "OID-1",
                            "title": "Paint by numbers",
                            "num": 2,
                            "price": 12.5,
                            "outerIid": "PBN-LD000001-3040-24-U",
                            "shopMappingSku": "PBN-LD000001-3040-24-U",
                            "originalSkuId": "10832717802",
                            "originalGoodsId": "goods-1",
                            "cancelStatus": False,
                        }
                    ],
                },
                "msg": "",
            },
        )

    http_client = _client(httpx.MockTransport(handler))
    client = FangguoClient(
        FangguoSettings(),
        api_key=SecretStr("test-key"),
        http_client=http_client,
    )
    page = await client.list_order_tids(
        FangguoTidListRequest(start_time=1, end_time=2, platform_type=225)
    )
    detail = await client.get_order_detail(page.items[0].tid)
    assert page.total == 1
    assert detail.fulfillment_status == 4
    assert detail.items[0].shop_mapping_sku == "PBN-LD000001-3040-24-U"
    assert len(requests) == 2
    await http_client.aclose()


@pytest.mark.asyncio
async def test_retries_transient_http_status_without_exposing_key() -> None:
    calls = 0
    delays: list[float] = []

    async def sleep(delay: float) -> None:
        delays.append(delay)

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, json={"code": 503, "msg": "unavailable"})
        return httpx.Response(200, json={"code": 0, "data": {"list": []}, "msg": ""})

    http_client = _client(httpx.MockTransport(handler))
    client = FangguoClient(
        FangguoSettings(max_attempts=2),
        api_key=SecretStr("do-not-leak"),
        http_client=http_client,
        sleep=sleep,
    )
    assert await client.list_stores() == []
    assert calls == 2
    assert delays == [1.0]
    assert "do-not-leak" not in repr(client)
    await http_client.aclose()


@pytest.mark.asyncio
async def test_raises_business_error_and_missing_key_error() -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 1005001011, "data": None, "msg": "订单不存在"})

    with pytest.raises(FangguoConfigurationError):
        FangguoClient(FangguoSettings())

    http_client = _client(httpx.MockTransport(handler))
    client = FangguoClient(
        FangguoSettings(),
        api_key=SecretStr("test-key"),
        http_client=http_client,
    )
    with pytest.raises(FangguoResponseError) as exc_info:
        await client.get_order_detail("missing")
    assert exc_info.value.code == 1005001011
    await http_client.aclose()

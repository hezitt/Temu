import base64
import gzip
import json
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from core.config import SorftimeSettings
from integrations.sorftime.client import (
    SorftimeBudgetExceededError,
    SorftimeClient,
    SorftimeLiveRequestsDisabledError,
    SorftimeResponseError,
    decode_response_payload,
)
from integrations.sorftime.schemas import ProductSearchRequest


def _encoded(payload: dict[str, object]) -> bytes:
    raw = json.dumps(payload).encode("utf-8")
    return base64.b64encode(gzip.compress(raw))


def test_decodes_base64_gzip_and_plain_json() -> None:
    payload = {
        "RequestLeft": 49,
        "RequestConsumed": 1,
        "Code": 0,
        "Message": None,
        "Data": [{"NodeId": "123"}],
    }
    assert decode_response_payload(_encoded(payload)) == payload
    assert decode_response_payload(json.dumps(payload).encode()) == payload


@pytest.mark.asyncio
async def test_lowercase_business_error_is_recorded_conservatively(tmp_path: Path) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 11, "message": "No data available"})

    http_client = httpx.AsyncClient(
        base_url="https://standardapi.sorftime.test/api",
        transport=httpx.MockTransport(handler),
    )
    client = SorftimeClient(
        SorftimeSettings(
            live_requests_enabled=True,
            request_budget=50,
            cache_dir=tmp_path,
        ),
        account_sk=SecretStr("test-sk"),
        http_client=http_client,
    )
    with pytest.raises(SorftimeResponseError) as exc_info:
        await client.search_categories("成人数字画套件")
    assert exc_info.value.code == 11
    assert client.estimated_remaining_budget() == 49
    ledger = json.loads((tmp_path / "request-ledger.jsonl").read_text(encoding="utf-8"))
    assert ledger["request_consumed"] == 1
    assert ledger["reported_request_consumed"] is None
    await http_client.aclose()


@pytest.mark.asyncio
async def test_live_call_uses_basic_auth_and_cache_prevents_second_call(tmp_path: Path) -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert request.headers["Authorization"] == "BasicAuth test-sk"
        assert request.url.params["domain"] == "701"
        assert json.loads(request.content) == {"Name": "Adult Paint by Number Kits"}
        return httpx.Response(
            200,
            content=_encoded(
                {
                    "RequestLeft": 49,
                    "RequestConsumed": 1,
                    "Code": 0,
                    "Message": None,
                    "Data": [{"NodeId": "123", "CategoryName": "Paint by Number Kits"}],
                }
            ),
        )

    http_client = httpx.AsyncClient(
        base_url="https://standardapi.sorftime.test/api",
        transport=httpx.MockTransport(handler),
    )
    settings = SorftimeSettings(
        live_requests_enabled=True,
        request_budget=50,
        cache_dir=tmp_path,
    )
    client = SorftimeClient(
        settings,
        account_sk=SecretStr("test-sk"),
        http_client=http_client,
    )
    first = await client.search_categories("Adult Paint by Number Kits")
    second = await client.search_categories("Adult Paint by Number Kits")
    assert first.data == second.data
    assert calls == 1
    assert client.estimated_remaining_budget() == 49
    assert len(list((tmp_path / "responses").glob("*.json"))) == 1
    assert len(list((tmp_path / "snapshots" / "CategorySearchFromName").glob("*.json"))) == 1
    await http_client.aclose()


@pytest.mark.asyncio
async def test_live_requests_are_off_by_default(tmp_path: Path) -> None:
    client = SorftimeClient(SorftimeSettings(cache_dir=tmp_path))
    with pytest.raises(SorftimeLiveRequestsDisabledError):
        await client.search_categories("Paint by Number Kits")
    await client.close()


@pytest.mark.asyncio
async def test_budget_guard_blocks_expensive_request(tmp_path: Path) -> None:
    client = SorftimeClient(
        SorftimeSettings(
            live_requests_enabled=True,
            request_budget=4,
            cache_dir=tmp_path,
        ),
        account_sk=SecretStr("test-sk"),
    )
    with pytest.raises(SorftimeBudgetExceededError):
        await client.search_products(ProductSearchRequest(NodeId="123", ManageType=1))
    await client.close()


def test_product_search_rejects_invalid_ranges() -> None:
    with pytest.raises(ValueError):
        ProductSearchRequest(PriceMin=20, PriceMax=10)

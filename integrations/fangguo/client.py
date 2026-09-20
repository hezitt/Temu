import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from pydantic import SecretStr, ValidationError

from core.config import FangguoSettings
from integrations.fangguo.schemas import (
    FangguoEnvelope,
    FangguoFactory,
    FangguoOrderDetail,
    FangguoStore,
    FangguoTidListRequest,
    FangguoTidPage,
)


class FangguoClientError(RuntimeError):
    """Base error raised by the read-only Fangguo client."""


class FangguoConfigurationError(FangguoClientError):
    pass


class FangguoTransportError(FangguoClientError):
    pass


class FangguoResponseError(FangguoClientError):
    def __init__(self, *, code: int, message: str) -> None:
        super().__init__(f"Fangguo API returned code {code}: {message or 'unknown error'}")
        self.code = code
        self.message = message


class FangguoClient:
    """Read-only merchant API client.

    This boundary intentionally exposes no order creation, cancellation, shipment,
    or mutation methods.
    """

    _RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    def __init__(
        self,
        settings: FangguoSettings,
        *,
        api_key: SecretStr | None = None,
        http_client: httpx.AsyncClient | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        secret = api_key or settings.api_key
        if secret is None or not secret.get_secret_value().strip():
            raise FangguoConfigurationError("Fangguo API key is not configured")
        self.settings = settings
        self._api_key = secret.get_secret_value().strip()
        self._sleep = sleep
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            base_url=settings.base_url,
            timeout=httpx.Timeout(settings.request_timeout_seconds),
        )

    async def __aenter__(self) -> "FangguoClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def list_stores(self) -> list[FangguoStore]:
        data = await self._request("GET", "/shop/store/list")
        rows = _extract_rows(data)
        return _validate_rows(rows, FangguoStore, "store list")

    async def list_bound_factories(self) -> list[FangguoFactory]:
        data = await self._request("GET", "/basic/bindFactory/v1")
        rows = _extract_rows(data)
        return _validate_rows(rows, FangguoFactory, "factory list")

    async def list_order_tids(self, request: FangguoTidListRequest) -> FangguoTidPage:
        data = await self._request(
            "POST",
            "/order/tidList",
            json=request.model_dump(by_alias=True, exclude_none=True),
        )
        try:
            return FangguoTidPage.model_validate(data)
        except ValidationError as exc:
            raise FangguoTransportError("Invalid Fangguo order TID page") from exc

    async def get_order_detail(self, tid: str) -> FangguoOrderDetail:
        normalized_tid = tid.strip()
        if not normalized_tid or len(normalized_tid) > 255:
            raise ValueError("tid must contain between 1 and 255 characters")
        data = await self._request("GET", "/order/detail", params={"tid": normalized_tid})
        try:
            return FangguoOrderDetail.model_validate(data)
        except ValidationError as exc:
            raise FangguoTransportError("Invalid Fangguo order detail") from exc

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, self.settings.max_attempts + 1):
            try:
                response = await self._client.request(
                    method,
                    path,
                    params=params,
                    json=json,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                )
            except httpx.RequestError as exc:
                last_error = exc
                if attempt == self.settings.max_attempts:
                    break
                await self._sleep(float(2 ** (attempt - 1)))
                continue

            if response.status_code in self._RETRYABLE_STATUS_CODES:
                last_error = FangguoTransportError(
                    f"Fangguo API temporarily unavailable (HTTP {response.status_code})"
                )
                if attempt == self.settings.max_attempts:
                    break
                await self._sleep(float(2 ** (attempt - 1)))
                continue
            try:
                response.raise_for_status()
                envelope = FangguoEnvelope.model_validate(response.json())
            except (httpx.HTTPStatusError, ValueError, ValidationError) as exc:
                raise FangguoTransportError(
                    f"Invalid Fangguo HTTP response (HTTP {response.status_code})"
                ) from exc
            if envelope.code != 0:
                raise FangguoResponseError(code=envelope.code, message=envelope.msg)
            return envelope.data

        raise FangguoTransportError(
            f"Fangguo API request failed after {self.settings.max_attempts} attempts"
        ) from last_error


def _extract_rows(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        rows = data.get("list")
        if isinstance(rows, list):
            return rows
        if "factoryId" in data:
            return [data]
    raise FangguoTransportError("Fangguo response does not contain a list")


def _validate_rows[T](rows: list[Any], model: type[T], description: str) -> list[T]:
    try:
        return [model.model_validate(row) for row in rows]  # type: ignore[attr-defined]
    except (AttributeError, ValidationError) as exc:
        raise FangguoTransportError(f"Invalid Fangguo {description}") from exc

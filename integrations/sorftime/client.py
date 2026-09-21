import base64
import gzip
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from pydantic import SecretStr, ValidationError

from core.config import SorftimeSettings
from integrations.sorftime.schemas import (
    CategoryRequest,
    CategorySearchFromNameRequest,
    ProductRequest,
    ProductSearchFromNameRequest,
    ProductSearchRequest,
    ProductTrendRequest,
    RequestPlan,
    SorftimeEnvelope,
    SorftimeModel,
)


class SorftimeClientError(RuntimeError):
    pass


class SorftimeConfigurationError(SorftimeClientError):
    pass


class SorftimeLiveRequestsDisabledError(SorftimeClientError):
    pass


class SorftimeBudgetExceededError(SorftimeClientError):
    pass


class SorftimeTransportError(SorftimeClientError):
    pass


class SorftimeResponseError(SorftimeClientError):
    def __init__(self, *, code: int, message: str) -> None:
        super().__init__(f"Sorftime API returned code {code}: {message or 'unknown error'}")
        self.code = code
        self.message = message


class SorftimeClient:
    """Temu market-data client with persistent cache and request-budget protection.

    Live calls are disabled by default. Cached responses remain readable while live
    access is disabled, so analysis never needs to spend the same credits twice.
    """

    ENDPOINT_COSTS = {
        "CategoryTree": 5,
        "CategorySearchFromName": 1,
        "CategoryRequest": 5,
        "ProductRequest": 1,
        "ProductSearchFromName": 2,
        "ProductTrendRequest": 5,
        "ProductSearch": 5,
    }

    def __init__(
        self,
        settings: SorftimeSettings,
        *,
        domain: int | None = None,
        account_sk: SecretStr | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self.domain = settings.domain if domain is None else domain
        if self.domain not in {*range(1, 15), 701, 705}:
            raise SorftimeConfigurationError(f"Unsupported Sorftime domain: {self.domain}")
        self._secret = account_sk or settings.account_sk
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            base_url=settings.base_url,
            timeout=httpx.Timeout(settings.request_timeout_seconds),
        )
        self._cache_dir = settings.cache_dir
        self._response_dir = self._cache_dir / "responses"
        self._ledger_path = self._cache_dir / "request-ledger.jsonl"

    async def __aenter__(self) -> "SorftimeClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def plan(
        self,
        endpoint: str,
        request: SorftimeModel,
        *,
        cost_override: int | None = None,
    ) -> RequestPlan:
        body = request.model_dump(by_alias=True, exclude_none=True)
        return self._build_plan(endpoint, body, cost_override=cost_override)

    async def request_endpoint(
        self,
        endpoint: str,
        request: SorftimeModel,
        *,
        cost_override: int | None = None,
    ) -> SorftimeEnvelope:
        return await self._request(endpoint, request, cost_override=cost_override)

    async def get_category_tree(self) -> SorftimeEnvelope:
        return await self._request("CategoryTree", SorftimeModel())

    async def search_categories(self, name: str) -> SorftimeEnvelope:
        return await self._request(
            "CategorySearchFromName", CategorySearchFromNameRequest(name=name)
        )

    async def get_category(self, node_id: str) -> SorftimeEnvelope:
        return await self._request("CategoryRequest", CategoryRequest(node_id=node_id))

    async def get_product(self, product_id: str) -> SorftimeEnvelope:
        return await self._request("ProductRequest", ProductRequest(product_id=product_id))

    async def search_products_by_name(self, name: str, *, page: int = 1) -> SorftimeEnvelope:
        return await self._request(
            "ProductSearchFromName", ProductSearchFromNameRequest(name=name, page=page)
        )

    async def get_product_trend(self, product_id: str) -> SorftimeEnvelope:
        return await self._request(
            "ProductTrendRequest", ProductTrendRequest(product_id=product_id)
        )

    async def search_products(self, request: ProductSearchRequest) -> SorftimeEnvelope:
        return await self._request("ProductSearch", request)

    def estimated_remaining_budget(self) -> int:
        consumed = 0
        server_remaining: int | None = None
        if self._ledger_path.exists():
            for line in self._ledger_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                    consumed += int(row["request_consumed"])
                    if row.get("request_left") is not None:
                        server_remaining = int(row["request_left"])
                except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                    continue
        local_remaining = max(0, self.settings.request_budget - consumed)
        if server_remaining is None:
            return local_remaining
        return min(local_remaining, max(0, server_remaining))

    async def _request(
        self,
        endpoint: str,
        request: SorftimeModel,
        *,
        cost_override: int | None = None,
    ) -> SorftimeEnvelope:
        plan = self.plan(endpoint, request, cost_override=cost_override)
        cached = self._read_cache(plan.cache_key)
        if cached is not None:
            return cached

        if not self.settings.live_requests_enabled:
            raise SorftimeLiveRequestsDisabledError(
                f"Live Sorftime requests are disabled; planned {endpoint} costs {plan.cost}"
            )
        if self.estimated_remaining_budget() < plan.cost:
            raise SorftimeBudgetExceededError(
                f"Sorftime request budget is too low for {endpoint} (cost={plan.cost})"
            )
        if self._secret is None or not self._secret.get_secret_value().strip():
            raise SorftimeConfigurationError("Sorftime Account-SK is not configured")

        try:
            response = await self._client.post(
                f"/{endpoint}",
                params={"domain": self.domain},
                json=plan.body,
                headers={
                    "Authorization": f"BasicAuth {self._secret.get_secret_value().strip()}",
                    "Accept": "application/json",
                    "Content-Type": "application/json;charset=UTF-8",
                },
            )
            response.raise_for_status()
            payload = decode_response_payload(response.content)
            envelope = SorftimeEnvelope.model_validate(payload)
        except (httpx.HTTPError, ValueError, OSError, ValidationError) as exc:
            raise SorftimeTransportError(
                f"Invalid Sorftime response for {endpoint}"
            ) from exc

        self._record_live_response(plan, envelope)
        if envelope.code != 0:
            raise SorftimeResponseError(
                code=envelope.code,
                message=envelope.message or "unknown error",
            )
        self._write_cache(plan, envelope)
        return envelope

    def _build_plan(
        self,
        endpoint: str,
        body: dict[str, Any],
        *,
        cost_override: int | None = None,
    ) -> RequestPlan:
        if cost_override is not None:
            if cost_override < 0:
                raise ValueError("Sorftime request cost cannot be negative")
            cost = cost_override
        else:
            try:
                cost = self.ENDPOINT_COSTS[endpoint]
            except KeyError as exc:
                raise ValueError(f"Unsupported Sorftime endpoint: {endpoint}") from exc
        canonical = json.dumps(
            {"domain": self.domain, "endpoint": endpoint, "body": body},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        cache_key = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return RequestPlan(
            endpoint=endpoint,
            cost=cost,
            domain=self.domain,
            body=body,
            cache_key=cache_key,
        )

    def _cache_path(self, cache_key: str) -> Path:
        return self._response_dir / f"{cache_key}.json"

    def _read_cache(self, cache_key: str) -> SorftimeEnvelope | None:
        path = self._cache_path(cache_key)
        if not path.exists():
            return None
        age_seconds = datetime.now(UTC).timestamp() - path.stat().st_mtime
        if age_seconds > self.settings.cache_ttl_hours * 3600:
            return None
        try:
            return SorftimeEnvelope.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError, ValueError) as exc:
            raise SorftimeTransportError(f"Invalid Sorftime cache file: {path}") from exc

    def _write_cache(self, plan: RequestPlan, envelope: SorftimeEnvelope) -> None:
        self._response_dir.mkdir(parents=True, exist_ok=True)
        payload = envelope.model_dump_json(by_alias=True, indent=2)
        self._cache_path(plan.cache_key).write_text(payload, encoding="utf-8")
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        snapshot_dir = self._cache_dir / "snapshots" / plan.endpoint
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = snapshot_dir / f"{timestamp}-{plan.cache_key[:12]}.json"
        snapshot_path.write_text(payload, encoding="utf-8")

    def _record_live_response(self, plan: RequestPlan, envelope: SorftimeEnvelope) -> None:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        effective_consumed = envelope.request_consumed
        if effective_consumed is None:
            effective_consumed = plan.cost
        row = {
            "timestamp": datetime.now(UTC).isoformat(),
            "endpoint": plan.endpoint,
            "domain": plan.domain,
            "cache_key": plan.cache_key,
            "planned_cost": plan.cost,
            "request_consumed": effective_consumed,
            "reported_request_consumed": envelope.request_consumed,
            "request_left": envelope.request_left,
            "code": envelope.code,
        }
        with self._ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def decode_response_payload(content: bytes) -> Any:
    """Decode either a normal JSON response or Sorftime's base64+gzip envelope."""

    stripped = content.strip()
    if not stripped:
        raise ValueError("Sorftime returned an empty response")

    try:
        decoded_json = json.loads(stripped)
    except json.JSONDecodeError:
        decoded_json = None
    if isinstance(decoded_json, dict):
        return decoded_json
    encoded = decoded_json if isinstance(decoded_json, str) else stripped.decode("ascii")
    compressed = base64.b64decode(encoded, validate=True)
    raw_json = gzip.decompress(compressed)
    return json.loads(raw_json)

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ObservedSkuMapping(BaseModel):
    model_config = ConfigDict(frozen=True)

    sku_item_code: str = Field(min_length=1)
    temu_sku_id: str = Field(min_length=1)

    @field_validator("sku_item_code", "temu_sku_id")
    @classmethod
    def strip_identifier(cls, value: str) -> str:
        return value.strip()


class DianxiaomiListingObservation(BaseModel):
    model_config = ConfigDict(frozen=True)

    internal_spu_item_code: str = Field(min_length=1)
    dianxiaomi_spu_id: str = Field(min_length=1)
    temu_spu_id: str | None = None
    temu_skc_id: str = Field(min_length=1)
    marketplace: str = "US"
    review_status: str | None = None
    lifecycle_status: str | None = None
    seller_center_confirmation_pending: bool = True
    submission_channel: str = "DIANXIAOMI_MANUAL"
    observed_at: datetime | None = None
    source_file_name: str
    source_sha256: str = Field(min_length=64, max_length=64)
    sku_mappings: list[ObservedSkuMapping] = Field(min_length=1)
    raw_payload: dict[str, Any]

    @field_validator(
        "internal_spu_item_code",
        "dianxiaomi_spu_id",
        "temu_spu_id",
        "temu_skc_id",
        "marketplace",
        "review_status",
        "lifecycle_status",
        "submission_channel",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @model_validator(mode="after")
    def unique_sku_mappings(self) -> "DianxiaomiListingObservation":
        item_codes = [mapping.sku_item_code for mapping in self.sku_mappings]
        temu_sku_ids = [mapping.temu_sku_id for mapping in self.sku_mappings]
        if len(set(item_codes)) != len(item_codes):
            raise ValueError("Duplicate internal SKU item codes in Dianxiaomi observation")
        if len(set(temu_sku_ids)) != len(temu_sku_ids):
            raise ValueError("Duplicate Temu SKU IDs in Dianxiaomi observation")
        return self


def load_dianxiaomi_listing_observation(
    path: Path, *, observed_at: datetime | None = None
) -> DianxiaomiListingObservation:
    source = path.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    raw_bytes = source.read_bytes()
    try:
        payload = json.loads(raw_bytes)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid listing intake JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Listing intake JSON must contain an object")

    identifiers = _require_object(payload, "identifiers")
    external = _require_object(payload, "external_identifiers_observed_in_dianxiaomi")
    submission = _require_object(payload, "submission")
    mappings = external.get("sku_mappings")
    if not isinstance(mappings, list) or not mappings:
        raise ValueError("Dianxiaomi observation must contain sku_mappings")
    if any(not isinstance(mapping, dict) for mapping in mappings):
        raise ValueError("Every Dianxiaomi sku_mappings entry must be an object")

    dianxiaomi_spu = _required_text(identifiers, "dianxiaomi_spu")
    observed_spu = _required_text(external, "spu_id")
    if dianxiaomi_spu != observed_spu:
        raise ValueError("identifiers.dianxiaomi_spu does not match the observed SPU ID")

    return DianxiaomiListingObservation(
        internal_spu_item_code=_required_text(identifiers, "internal_spu_item_code"),
        dianxiaomi_spu_id=observed_spu,
        temu_spu_id=_optional_text(identifiers.get("temu_spu")),
        temu_skc_id=_required_text(external, "skc_id"),
        marketplace=_optional_text(payload.get("marketplace")) or "US",
        review_status=_optional_text(submission.get("review_status")),
        lifecycle_status=_optional_text(submission.get("lifecycle_displayed")),
        seller_center_confirmation_pending=bool(
            external.get("temu_seller_center_confirmation_pending", True)
        ),
        submission_channel=_optional_text(submission.get("channel"))
        or "DIANXIAOMI_MANUAL",
        observed_at=observed_at
        or datetime.fromtimestamp(source.stat().st_mtime, tz=UTC),
        source_file_name=source.name,
        source_sha256=hashlib.sha256(raw_bytes).hexdigest(),
        sku_mappings=[
            ObservedSkuMapping(
                sku_item_code=_required_text(mapping, "sku_item_code"),
                temu_sku_id=_required_text(mapping, "sku_id"),
            )
            for mapping in mappings
        ],
        raw_payload=payload,
    )


def _require_object(payload: dict[str, Any], field: str) -> dict[str, Any]:
    value = payload.get(field)
    if not isinstance(value, dict):
        raise ValueError(f"Listing intake is missing object: {field}")
    return value


def _required_text(payload: dict[str, Any], field: str) -> str:
    value = _optional_text(payload.get(field))
    if value is None:
        raise ValueError(f"Listing intake is missing text field: {field}")
    return value


def _optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None

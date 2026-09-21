from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field, SecretStr, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)


class PricingSettings(BaseModel):
    target_margin: float = Field(default=0.35, gt=0, lt=1)
    min_margin: float = Field(default=0.30, ge=0, lt=1)
    default_currency: str = Field(default="CNY", min_length=3, max_length=3)
    require_dry_run: bool = True

    @model_validator(mode="after")
    def validate_margin_order(self) -> "PricingSettings":
        if self.min_margin >= self.target_margin:
            raise ValueError("pricing.min_margin must be lower than pricing.target_margin")
        self.default_currency = self.default_currency.upper()
        return self


class ImportSettings(BaseModel):
    factory_quote_currency: str = Field(default="CNY", min_length=3, max_length=3)
    unavailable_markers: list[str] = Field(default_factory=lambda: ["/", "-", "N/A"])
    zero_price_is_invalid: bool = True

    @model_validator(mode="after")
    def normalize_currency(self) -> "ImportSettings":
        self.factory_quote_currency = self.factory_quote_currency.upper()
        return self


class FactoryQuoteSettings(BaseModel):
    product_type: str = "PAINT_BY_NUMBERS"
    allowed_color_counts: set[int] = Field(default_factory=lambda: {16, 24, 36, 48, 60})
    suspicious_low_ratio: float = Field(default=0.60, gt=0, lt=1)
    size_inversion_ratio: float = Field(default=0.90, gt=0, le=1)
    color_inversion_ratio: float = Field(default=0.90, gt=0, le=1)


class SupplierProfile(BaseModel):
    name: str
    currency: str = Field(min_length=3, max_length=3)
    country_code: str = Field(min_length=2, max_length=2)
    timezone: str = "America/Los_Angeles"

    @model_validator(mode="after")
    def normalize_codes(self) -> "SupplierProfile":
        self.currency = self.currency.upper()
        self.country_code = self.country_code.upper()
        return self


class ReportSettings(BaseModel):
    node_executable: str = "node"


class CostingSettings(BaseModel):
    estimated_shipping_cost_usd: Decimal = Field(default=Decimal("4.00"), ge=0)
    usd_cny_exchange_rate: Decimal | None = Field(default=None, gt=0)
    exchange_rate_source: str = "MANUAL_CONFIG"
    exchange_rate_timestamp: datetime | None = None
    label_service_cost_cny: Decimal = Field(default=Decimal("0.00"), ge=0)
    label_service_cost_status: str = "CONFIRMED"

    @model_validator(mode="after")
    def validate_exchange_rate_metadata(self) -> "CostingSettings":
        if self.usd_cny_exchange_rate is not None and self.exchange_rate_timestamp is None:
            raise ValueError(
                "costing.exchange_rate_timestamp is required when an exchange rate is configured"
            )
        return self


class ListingSettings(BaseModel):
    product_type: str = "PAINT_BY_NUMBERS"
    target_market: str = "US"
    require_existing_main_image: bool = True


class FangguoSettings(BaseModel):
    base_url: str = "https://open.fangguo.com/fgapp/openapi"
    api_key: SecretStr | None = None
    request_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    max_attempts: int = Field(default=3, ge=1, le=5)
    platform_type: int = 225
    page_size: int = Field(default=100, ge=1, le=100)
    rolling_lookback_minutes: int = Field(default=180, ge=5, le=1440)

    @model_validator(mode="after")
    def normalize_base_url(self) -> "FangguoSettings":
        self.base_url = self.base_url.rstrip("/")
        return self


class SorftimeSettings(BaseModel):
    base_url: str = "https://standardapi.sorftime.com/api"
    account_sk: SecretStr | None = None
    domain: int = Field(default=701, description="701=US, 705=Europe")
    request_timeout_seconds: float = Field(default=120.0, gt=0, le=300)
    request_budget: int = Field(default=50, ge=0)
    live_requests_enabled: bool = False
    cache_dir: Path = Path("data/processed/sorftime")
    cache_ttl_hours: int = Field(default=24, ge=1, le=720)

    @model_validator(mode="after")
    def validate_sorftime_settings(self) -> "SorftimeSettings":
        self.base_url = self.base_url.rstrip("/")
        if self.domain not in {701, 705}:
            raise ValueError("sorftime.domain must be 701 (US) or 705 (Europe)")
        return self


class PathSettings(BaseModel):
    raw_data_dir: Path = Path("data/raw")
    processed_data_dir: Path = Path("data/processed")
    output_dir: Path = Path("outputs")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        yaml_file="settings.yaml",
        extra="ignore",
    )

    app_name: str = "Temu PBN Automation"
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://temu_pbn:change-me@localhost:5432/temu_pbn"
    pricing: PricingSettings = Field(default_factory=PricingSettings)
    imports: ImportSettings = Field(default_factory=ImportSettings)
    factory_quotes: FactoryQuoteSettings = Field(default_factory=FactoryQuoteSettings)
    costing: CostingSettings = Field(default_factory=CostingSettings)
    listing: ListingSettings = Field(default_factory=ListingSettings)
    fangguo: FangguoSettings = Field(default_factory=FangguoSettings)
    sorftime: SorftimeSettings = Field(default_factory=SorftimeSettings)
    supplier_profiles: dict[str, SupplierProfile] = Field(default_factory=dict)
    reports: ReportSettings = Field(default_factory=ReportSettings)
    paths: PathSettings = Field(default_factory=PathSettings)

    def supplier_profile(self, supplier_code: str) -> SupplierProfile:
        code = supplier_code.upper()
        try:
            return self.supplier_profiles[code]
        except KeyError as exc:
            raise ValueError(f"Supplier {code!r} is not configured in supplier_profiles") from exc

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()

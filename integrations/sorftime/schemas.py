from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator


class SorftimeModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class SorftimeEnvelope(SorftimeModel):
    request_left: int | None = Field(
        default=None,
        validation_alias=AliasChoices("RequestLeft", "requestLeft"),
        serialization_alias="RequestLeft",
    )
    request_consumed: int | None = Field(
        default=None,
        validation_alias=AliasChoices("RequestConsumed", "requestConsumed"),
        serialization_alias="RequestConsumed",
    )
    code: int = Field(
        validation_alias=AliasChoices("Code", "code"),
        serialization_alias="Code",
    )
    message: str | None = Field(
        default=None,
        validation_alias=AliasChoices("Message", "message"),
        serialization_alias="Message",
    )
    data: Any = Field(
        default=None,
        validation_alias=AliasChoices("Data", "data"),
        serialization_alias="Data",
    )


class CategorySearchFromNameRequest(SorftimeModel):
    name: str = Field(alias="Name", min_length=1, max_length=200)


class CategoryRequest(SorftimeModel):
    node_id: str = Field(alias="NodeId", min_length=1, max_length=100)


class ProductRequest(SorftimeModel):
    product_id: str = Field(alias="ProductId", min_length=1, max_length=100)


class ProductSearchFromNameRequest(SorftimeModel):
    name: str = Field(alias="Name", min_length=1, max_length=300)
    page: int = Field(default=1, alias="Page", ge=1)


class ProductTrendRequest(SorftimeModel):
    product_id: str = Field(alias="ProductId", min_length=1, max_length=100)


class ProductSearchRequest(SorftimeModel):
    node_id: str | None = Field(default=None, alias="NodeId")
    brand: str | None = Field(default=None, alias="Brand")
    seller_name: str | None = Field(default=None, alias="SellerName")
    cumulative_sale_count_min: int | None = Field(
        default=None, alias="CumulativeSaleCountMin", ge=0
    )
    cumulative_sale_count_max: int | None = Field(
        default=None, alias="CumulativeSaleCountMax", ge=0
    )
    sale_count_min: int | None = Field(default=None, alias="SaleCountMin", ge=0)
    sale_count_max: int | None = Field(default=None, alias="SaleCountMax", ge=0)
    sale_amount_min: float | None = Field(default=None, alias="SaleAmountMin", ge=0)
    sale_amount_max: float | None = Field(default=None, alias="SaleAmountMax", ge=0)
    sale_count_mom_min: float | None = Field(default=None, alias="SaleCountMoMMin")
    sale_count_mom_max: float | None = Field(default=None, alias="SaleCountMoMMax")
    price_min: float | None = Field(default=None, alias="PriceMin", ge=0)
    price_max: float | None = Field(default=None, alias="PriceMax", ge=0)
    manage_type: int | None = Field(default=None, alias="ManageType", ge=0, le=2)
    comment_count_min: int | None = Field(default=None, alias="CommentCountMin", ge=0)
    comment_count_max: int | None = Field(default=None, alias="CommentCountMax", ge=0)
    star_min: float | None = Field(default=None, alias="StarMin", ge=0, le=5)
    star_max: float | None = Field(default=None, alias="StarMax", ge=0, le=5)
    sale_time_min: str | None = Field(default=None, alias="SaleTimeMin")
    sale_time_max: str | None = Field(default=None, alias="SaleTimeMax")

    @model_validator(mode="after")
    def validate_ranges(self) -> "ProductSearchRequest":
        pairs = (
            (
                "cumulative_sale_count",
                self.cumulative_sale_count_min,
                self.cumulative_sale_count_max,
            ),
            ("sale_count", self.sale_count_min, self.sale_count_max),
            ("sale_amount", self.sale_amount_min, self.sale_amount_max),
            ("sale_count_mom", self.sale_count_mom_min, self.sale_count_mom_max),
            ("price", self.price_min, self.price_max),
            ("comment_count", self.comment_count_min, self.comment_count_max),
            ("star", self.star_min, self.star_max),
        )
        for name, minimum, maximum in pairs:
            if minimum is not None and maximum is not None and minimum > maximum:
                raise ValueError(f"{name}_min must not exceed {name}_max")
        if (
            self.sale_time_min is not None
            and self.sale_time_max is not None
            and self.sale_time_min > self.sale_time_max
        ):
            raise ValueError("sale_time_min must not exceed sale_time_max")
        return self


class RequestPlan(SorftimeModel):
    endpoint: str
    cost: int
    domain: int
    body: dict[str, Any]
    cache_key: str

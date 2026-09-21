from datetime import date

from pydantic import Field, model_validator

from integrations.sorftime.schemas import SorftimeModel


class AmazonCategoryRequest(SorftimeModel):
    node_id: str = Field(alias="NodeId", min_length=1, max_length=200)
    query_start: date | None = Field(default=None, alias="QueryStart")
    query_date: date | None = Field(default=None, alias="QueryDate")
    query_days: int | None = Field(default=None, alias="QueryDays", ge=3, le=40)

    @model_validator(mode="after")
    def validate_history_range(self) -> "AmazonCategoryRequest":
        if self.query_start is not None and self.query_date is None:
            raise ValueError("query_date is required when query_start is set")
        if self.query_days is not None and self.query_date is None:
            raise ValueError("query_date is required when query_days is set")
        if self.query_start is not None and self.query_days is not None:
            raise ValueError("use either query_start or query_days, not both")
        if (
            self.query_start is not None
            and self.query_date is not None
            and self.query_start > self.query_date
        ):
            raise ValueError("query_start must not be later than query_date")
        return self


class AmazonCategoryProductsRequest(SorftimeModel):
    node_id: str = Field(alias="NodeId", min_length=1, max_length=200)
    page: int = Field(default=1, alias="Page", ge=1)


class AmazonCategoryTrendRequest(SorftimeModel):
    node_id: str = Field(alias="NodeId", min_length=1, max_length=200)
    trend_index: int = Field(alias="TrendIndex", ge=0, le=39)


class AmazonProductRequest(SorftimeModel):
    asin: str = Field(alias="ASIN", min_length=10)
    trend: int = Field(default=1, alias="Trend", ge=1, le=2)
    query_trend_start: date | None = Field(default=None, alias="QueryTrendStartDt")
    query_trend_end: date | None = Field(default=None, alias="QueryTrendEndDt")

    @model_validator(mode="after")
    def validate_trend_range(self) -> "AmazonProductRequest":
        if self.query_trend_start is not None and self.trend != 1:
            raise ValueError("trend must be 1 when a trend date range is requested")
        if self.query_trend_end is not None and self.query_trend_start is None:
            raise ValueError("query_trend_start is required when query_trend_end is set")
        if (
            self.query_trend_start is not None
            and self.query_trend_end is not None
            and self.query_trend_start > self.query_trend_end
        ):
            raise ValueError("query_trend_start must not be later than query_trend_end")
        if len(self.asins) > 10:
            raise ValueError("Amazon ProductRequest supports at most 10 ASINs")
        return self

    @property
    def asins(self) -> list[str]:
        return [value.strip() for value in self.asin.split(",") if value.strip()]


class AmazonProductSearchFromNameRequest(SorftimeModel):
    name: str = Field(alias="Name", min_length=1, max_length=300)
    page_index: int = Field(default=1, alias="PageIndex", ge=1)


class AmazonProductSearchRequest(SorftimeModel):
    query_month: str | None = Field(default=None, alias="QueryMonth")
    page: int = Field(default=1, alias="Page", ge=1)
    asin: str | None = Field(default=None, alias="ASIN")
    node_id: str | None = Field(default=None, alias="NodeId")
    brand: str | None = Field(default=None, alias="Brand")
    seller_name: str | None = Field(default=None, alias="SellerName")
    seller_id: str | None = Field(default=None, alias="SellerId")
    keyword: str | None = Field(default=None, alias="Keyword")
    attribute_name: str | None = Field(default=None, alias="AttributeName")
    peak_selling_season: str | None = Field(default=None, alias="PeakSellingSeason")
    shipping_type: str | None = Field(default=None, alias="ShippingType")
    price_min: float | None = Field(default=None, alias="PriceRangeMin", ge=0)
    price_max: float | None = Field(default=None, alias="PriceRangeMax", ge=0)
    monthly_sales_min: int | None = Field(default=None, alias="MonthSaleVolumeRangeMin", ge=0)
    monthly_sales_max: int | None = Field(default=None, alias="MonthSaleVolumeRangeMax", ge=0)
    online_date_min: date | None = Field(default=None, alias="OnlineDateRangeMin")
    online_date_max: date | None = Field(default=None, alias="OnlineDateRangeMax")
    star_min: float | None = Field(default=None, alias="StarRangeMin", ge=0, le=5)
    star_max: float | None = Field(default=None, alias="StarRangeMax", ge=0, le=5)
    review_count_min: int | None = Field(default=None, alias="CommentCountRangeMin", ge=0)
    review_count_max: int | None = Field(default=None, alias="CommentCountRangeMax", ge=0)
    subcategory_rank_min: int | None = Field(
        default=None, alias="SubCategoryRankRangeMin", ge=1
    )
    subcategory_rank_max: int | None = Field(
        default=None, alias="SubCategoryRankRangeMax", ge=1
    )
    variation_count_min: int | None = Field(
        default=None, alias="VariationCountRangeMin", ge=0
    )
    variation_count_max: int | None = Field(
        default=None, alias="VariationCountRangeMax", ge=0
    )
    category_rank_min: int | None = Field(default=None, alias="CategoryRankRangeMin", ge=1)
    category_rank_max: int | None = Field(default=None, alias="CategoryRankRangeMax", ge=1)

    @model_validator(mode="after")
    def validate_ranges(self) -> "AmazonProductSearchRequest":
        pairs = (
            ("price", self.price_min, self.price_max),
            ("monthly_sales", self.monthly_sales_min, self.monthly_sales_max),
            ("star", self.star_min, self.star_max),
            ("review_count", self.review_count_min, self.review_count_max),
            ("subcategory_rank", self.subcategory_rank_min, self.subcategory_rank_max),
            ("variation_count", self.variation_count_min, self.variation_count_max),
            ("category_rank", self.category_rank_min, self.category_rank_max),
        )
        for name, minimum, maximum in pairs:
            if minimum is not None and maximum is not None and minimum > maximum:
                raise ValueError(f"{name}_min must not exceed {name}_max")
        if (
            self.online_date_min is not None
            and self.online_date_max is not None
            and self.online_date_min > self.online_date_max
        ):
            raise ValueError("online_date_min must not exceed online_date_max")
        return self


class AmazonAsinSalesVolumeRequest(SorftimeModel):
    asin: str = Field(alias="ASIN", min_length=10, max_length=20)
    page: int = Field(default=1, alias="Page", ge=1)
    query_date: date | None = Field(default=None, alias="QueryDate")
    query_end_date: date | None = Field(default=None, alias="QueryEndDate")


class AmazonProductVariationsRequest(SorftimeModel):
    asin: str = Field(alias="Asin", min_length=10, max_length=20)
    page_index: int = Field(default=1, alias="PageIndex", ge=1)
    include_sales_volume: bool = Field(default=False, alias="IsSalesVolume")


class AmazonProductCustomersSayRequest(SorftimeModel):
    asin: str = Field(alias="Asin", min_length=10, max_length=20)


class AmazonSimilarProductFeatureRequest(SorftimeModel):
    product_name: str = Field(alias="ProductName", min_length=1, max_length=300)


class AmazonKeywordRequest(SorftimeModel):
    keyword: str = Field(alias="Keyword", min_length=1, max_length=300)


class AmazonKeywordSearchResultsRequest(SorftimeModel):
    keyword: str = Field(alias="Keyword", min_length=1, max_length=300)
    position_type: int = Field(default=1, alias="PositionType", ge=0, le=2)
    page_index: int = Field(default=1, alias="PageIndex", ge=1)
    page_size: int = Field(default=20, alias="PageSize", ge=20, le=200)


class AmazonCategoryKeywordsRequest(SorftimeModel):
    node_id: str = Field(alias="Nodeid", min_length=1, max_length=200)
    page_index: int = Field(default=1, alias="PageIndex", ge=1)
    page_size: int = Field(default=20, alias="PageSize", ge=20, le=200)

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FangguoModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class FangguoEnvelope(FangguoModel):
    code: int
    data: Any = None
    msg: str = ""
    current_time: int | None = Field(default=None, alias="currentTime")


class FangguoStore(FangguoModel):
    id: int
    platform: int
    auth_id: str | None = Field(default=None, alias="authId")
    app_short_name: str | None = Field(default=None, alias="appShortName")
    nick: str
    brand_name: str | None = Field(default=None, alias="brandName")
    default_factory: int | None = Field(default=None, alias="defaultFactory")
    auto_sync: bool = Field(default=False, alias="autoSync")
    create_time: int | None = Field(default=None, alias="createTime")


class FangguoFactory(FangguoModel):
    factory_id: int = Field(alias="factoryId")
    factory_name: str = Field(alias="factoryName")


class FangguoTidListRequest(FangguoModel):
    factory_id: int | None = Field(default=None, alias="factoryId")
    shop_id: int | None = Field(default=None, alias="shopId")
    start_time: int | None = Field(default=None, alias="startTime")
    end_time: int | None = Field(default=None, alias="endTime")
    order_status: int | None = Field(default=None, alias="orderStatus", ge=0, le=5)
    platform_type: int = Field(default=225, alias="platformType")
    page_no: int = Field(default=1, alias="pageNo", ge=1)
    page_size: int = Field(default=100, alias="pageSize", ge=1, le=100)

    @model_validator(mode="after")
    def validate_time_range(self) -> "FangguoTidListRequest":
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.end_time < self.start_time
        ):
            raise ValueError("end_time must not be earlier than start_time")
        return self


class FangguoTid(FangguoModel):
    tid: str


class FangguoTidPage(FangguoModel):
    items: list[FangguoTid] = Field(default_factory=list, alias="list")
    total: int = 0
    cursor: str | None = None


class FangguoOrderItem(FangguoModel):
    id: str | None = None
    order_id: str | None = Field(default=None, alias="orderId")
    sys_oid: str | None = Field(default=None, alias="sysOid")
    oid: str | None = None
    title: str | None = None
    quantity: int = Field(default=0, alias="num", ge=0)
    price: Decimal | None = None
    sku_properties_name: str | None = Field(default=None, alias="skuPropertiesName")
    outer_iid: str | None = Field(default=None, alias="outerIid")
    shop_mapping_sku: str | None = Field(default=None, alias="shopMappingSku")
    original_sku_id: str | None = Field(default=None, alias="originalSkuId")
    original_goods_id: str | None = Field(default=None, alias="originalGoodsId")
    refund_status_description: str | None = Field(default=None, alias="refundStatusDesc")
    cancelled: bool = Field(default=False, alias="cancelStatus")
    picture_code: str | None = Field(default=None, alias="pictureCode")
    picture_code_path: str | None = Field(default=None, alias="pictureCodePath")
    production_picture_path: str | None = Field(default=None, alias="productionPicPath")
    logistics_order_number: str | None = Field(default=None, alias="logisticsOrderNum")
    logistics_company_code: str | None = Field(default=None, alias="logisticsCompanyCode")


class FangguoOrderDetail(FangguoModel):
    id: str
    order_type: int = Field(alias="orderType")
    factory_id: int | None = Field(default=None, alias="factoryId")
    system_tid: str | None = Field(default=None, alias="sysTid")
    tid: str
    platform: int
    fulfillment_status: int = Field(alias="dfStatus")
    external_status_description: str | None = Field(default=None, alias="outerOrderStatusDesc")
    platform_description: str | None = Field(default=None, alias="platformDesc")
    store_name: str | None = Field(default=None, alias="storeName")
    shop_remark: str | None = Field(default=None, alias="shopRemark")
    buyer_remark: str | None = Field(default=None, alias="buyerRemark")
    items: list[FangguoOrderItem] = Field(default_factory=list, alias="orderItems")

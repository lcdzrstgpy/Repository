"""订单相关请求 schema（契约 5.3 / 5.4）。"""

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class NewItemIn(BaseModel):
    product_name: str = Field(..., min_length=1, max_length=200)
    categories: list[str] = Field(..., min_length=3, max_length=3)
    spec: str | None = Field(None, max_length=200)
    image_url: str | None = Field(None, max_length=500)
    item_remark: str | None = Field(None, max_length=500)


class SalesOrderCreateIn(BaseModel):
    """创建订单。total_count / total_price 由后端汇总，不接受前端传值。"""

    no: str = Field(..., min_length=1, max_length=32, description="订单单号（店小秘订单号）")
    remark: str | None = Field(None, max_length=500, description="备注")
    sku_code: str | None = Field(None, max_length=64, description="已有货号")
    new_item: NewItemIn | None = None
    count: Decimal = Field(..., gt=0, description="下单数量")
    estimated_cost: Decimal = Field(Decimal("0"), ge=0, description="预计成本总额")


class SalesOrderCancelIn(BaseModel):
    """取消订单。"""

    cancel_reason: str | None = Field(None, max_length=255, description="取消原因")


class ClaimIn(BaseModel):
    """接单。"""

    warehouse_id: int = Field(..., gt=0, description="指派仓库 id")


class ShipIn(BaseModel):
    """发货。"""

    express_no: str = Field(..., min_length=1, max_length=64, description="物流单号")
    count: Decimal = Field(..., gt=0, description="本次发货数量")

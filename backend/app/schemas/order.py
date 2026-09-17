"""订单相关请求 schema（契约 5.3 / 5.4）。"""

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class OrderItemIn(BaseModel):
    """订单明细入参。"""

    sku_id: int = Field(..., gt=0, description="SKU id")
    count: Decimal = Field(..., gt=0, description="下单数量")
    price: Decimal = Field(..., ge=0, description="单价")


class SalesOrderCreateIn(BaseModel):
    """创建订单。total_count / total_price 由后端汇总，不接受前端传值。"""

    customer_id: int = Field(..., gt=0, description="客户 id")
    remark: str | None = Field(None, max_length=500, description="备注")
    items: list[OrderItemIn] = Field(..., min_length=1, description="订单明细，至少一条")

    @field_validator("items")
    @classmethod
    def check_items(cls, value: list[OrderItemIn]) -> list[OrderItemIn]:
        """明细不能为空，且同一 SKU 不允许重复行。"""
        if not value:
            raise ValueError("订单明细不能为空")
        sku_ids = [item.sku_id for item in value]
        if len(sku_ids) != len(set(sku_ids)):
            raise ValueError("订单明细中存在重复的 SKU")
        return value


class SalesOrderCancelIn(BaseModel):
    """取消订单。"""

    cancel_reason: str | None = Field(None, max_length=255, description="取消原因")


class ClaimIn(BaseModel):
    """接单。"""

    warehouse_id: int = Field(..., gt=0, description="指派仓库 id")


class ShipIn(BaseModel):
    """发货。"""

    express_no: str = Field(..., min_length=1, max_length=64, description="物流单号")

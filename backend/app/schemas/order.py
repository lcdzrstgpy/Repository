"""订单相关请求 schema（契约 19.1，覆盖 5.3 / 5.4）。

六阶段起运营不再从系统 SKU 库选商品，而是录入「外部平台订单号 + 自由文本商品名 +
货号或新品标记」，因此创建订单的请求体与一阶段完全不同。
"""

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator


MAX_ORDER_QUANTITY = 999_999_999_999


class OrderItemIn(BaseModel):
    """订单明细入参（契约 19.1）。

    `sku_code` 与 `is_new` 必须二选一：填了货号说明是系统里的老品，
    勾了新品说明系统里还没有货号，由仓储端后续创建。
    """

    product_name: str = Field(..., min_length=1, max_length=200, description="商品名（自由文本）")
    sku_code: str | None = Field(None, max_length=64, description="货号，与 is_new 二选一")
    is_new: int = Field(0, ge=0, le=1, description="是否新品：0 否 / 1 是，与 sku_code 二选一")
    count: int = Field(..., ge=1, le=MAX_ORDER_QUANTITY, description="下单数量（正整数）")
    expect_price: Decimal = Field(..., gt=0, description="预计成本单价")

    @field_validator("product_name", mode="before")
    @classmethod
    def strip_product_name(cls, value):
        """商品名去掉首尾空白；空串会被 min_length=1 拦下并报参数错误。"""
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("sku_code", mode="before")
    @classmethod
    def normalize_sku_code(cls, value):
        """货号去掉首尾空白；空串视为未填写（前端清空输入框时常传 ""）。"""
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class SalesOrderCreateIn(BaseModel):
    """创建订单（契约 19.1）。

    `no` 为运营录入的订单号，全局唯一；`total_count` / `total_price` 由后端按明细汇总，
    不接受前端传值。
    """

    no: str = Field(..., min_length=1, max_length=32, description="订单号（外部平台单号，唯一）")
    remark: str | None = Field(None, max_length=500, description="备注")
    items: list[OrderItemIn] = Field(..., min_length=1, description="订单明细，至少一条")

    @field_validator("no", mode="before")
    @classmethod
    def strip_no(cls, value):
        """订单号去空白，避免「 TB001 」与「TB001」被当成两个单号。"""
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def check_items(self) -> "SalesOrderCreateIn":
        """校验明细：货号与新品二选一，且同一订单内货号不允许重复。"""
        seen_sku_codes: set[str] = set()
        for item in self.items:
            has_code = bool(item.sku_code)
            is_new = bool(item.is_new)
            if has_code and is_new:
                raise ValueError(f"商品「{item.product_name}」不能同时填写货号和勾选新品")
            if not has_code and not is_new:
                raise ValueError(f"商品「{item.product_name}」必须填写货号或勾选新品")
            if has_code:
                if item.sku_code in seen_sku_codes:
                    raise ValueError(f"订单明细中存在重复的货号：{item.sku_code}")
                seen_sku_codes.add(item.sku_code)
        return self


class SalesOrderCancelIn(BaseModel):
    """取消订单。"""

    cancel_reason: str | None = Field(None, max_length=255, description="取消原因")


class ConfirmQuantityItemIn(BaseModel):
    """运营确认的单个订单明细数量。"""

    item_id: int = Field(..., gt=0, description="订单明细 id")
    count: int = Field(..., ge=1, le=MAX_ORDER_QUANTITY, description="最终出库数量（正整数）")


class ConfirmQuantityIn(BaseModel):
    """运营确认最终数量（25 → 30）。请求必须覆盖订单全部明细。"""

    items: list[ConfirmQuantityItemIn] = Field(..., min_length=1, description="全部订单明细的最终数量")

    @model_validator(mode="after")
    def check_unique_items(self) -> "ConfirmQuantityIn":
        item_ids = [item.item_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("确认数量的明细不能重复")
        return self


class ClaimIn(BaseModel):
    """接单。单仓模式不再需要选择仓库。"""


class ShipIn(BaseModel):
    """发货。"""

    express_no: str = Field(..., min_length=1, max_length=64, description="物流单号")

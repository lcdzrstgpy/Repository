"""采购相关 schema（契约 10.2 / 10.3）。

响应结构对齐契约 10.3，字段风格与 `app/schemas/serializers.py` 保持一致：
datetime 格式化为 "YYYY-MM-DD HH:MM:SS"、date 格式化为 "YYYY-MM-DD"、Decimal 转 float。
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.models.basic import Product, ProductSku
from app.models.purchase import (
    PurchaseIn,
    PurchaseInItem,
    PurchaseOrder,
    PurchaseOrderItem,
    purchase_in_status_text,
    purchase_status_text,
)
from app.schemas.serializers import fmt_dec, fmt_dt


# ---------------------------------------------------------------- 请求
class PurchaseItemIn(BaseModel):
    """采购明细入参。"""

    sku_id: int = Field(..., gt=0, description="SKU id")
    count: Decimal = Field(..., gt=0, description="采购数量")
    price: Decimal = Field(..., ge=0, description="单价")


class PurchaseOrderCreateIn(BaseModel):
    """创建采购单。total_count / total_price 由后端汇总，不接受前端传值。"""

    sales_order_id: int | None = Field(None, gt=0, description="关联销售订单 id（因缺货采购时传）")
    express_no: str | None = Field(None, max_length=64, description="采购快递单号")
    remark: str | None = Field(None, max_length=500, description="备注")
    items: list[PurchaseItemIn] = Field(..., min_length=1, description="采购明细，至少一条")

    @field_validator("items")
    @classmethod
    def check_items(cls, value: list[PurchaseItemIn]) -> list[PurchaseItemIn]:
        """明细不能为空，且同一 SKU 不允许重复行。"""
        if not value:
            raise ValueError("采购明细不能为空")
        sku_ids = [item.sku_id for item in value]
        if len(sku_ids) != len(set(sku_ids)):
            raise ValueError("采购明细中存在重复的 SKU")
        return value


class PurchaseReceiveItemIn(BaseModel):
    """收货入库明细入参。count 为**本次**入库量，不是累计量。"""

    order_item_id: int = Field(..., gt=0, description="采购明细 id")
    count: Decimal = Field(..., gt=0, description="本次入库数量")


class PurchaseReceiveIn(BaseModel):
    """收货入库。"""

    express_no: str | None = Field(None, max_length=64, description="采购快递单号（可补填）")
    remark: str | None = Field(None, max_length=500, description="备注")
    items: list[PurchaseReceiveItemIn] = Field(..., min_length=1, description="入库明细，至少一条")

    @field_validator("items")
    @classmethod
    def check_items(cls, value: list[PurchaseReceiveItemIn]) -> list[PurchaseReceiveItemIn]:
        """明细不能为空，且同一采购明细不允许重复行。"""
        if not value:
            raise ValueError("入库明细不能为空")
        item_ids = [item.order_item_id for item in value]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("入库明细中存在重复的采购明细行")
        return value


# ---------------------------------------------------------------- 响应
def fmt_date(value: date | None) -> str | None:
    """日期格式化，None 原样返回。"""
    if value is None:
        return None
    return value.strftime("%Y-%m-%d")


def purchase_order_item_out(
    item: PurchaseOrderItem, sku: ProductSku | None = None, product: Product | None = None
) -> dict:
    """采购单明细元素（契约 10.3 详情 items）。"""
    return {
        "id": item.id,
        "order_id": item.order_id,
        "sku_id": item.sku_id,
        "sku_code": sku.sku_code if sku else None,
        "product_name": product.name if product else None,
        "spec": sku.spec if sku else None,
        "count": fmt_dec(item.count),
        "in_count": fmt_dec(item.in_count),
        "price": fmt_dec(item.price),
        "total_price": fmt_dec(item.total_price),
    }


def purchase_order_brief(
    order: PurchaseOrder,
    supplier_name: str | None = None,
    sales_order_no: str | None = None,
    warehouse_name: str | None = None,
    created_by_name: str | None = None,
    approved_by_name: str | None = None,
) -> dict:
    """采购单列表元素（契约 10.3 列表元素结构）。"""
    return {
        "id": order.id,
        "no": order.no,
        "sales_order_no": sales_order_no,
        "status": int(order.status) if order.status is not None else 0,
        "status_text": purchase_status_text(order.status),
        "total_count": fmt_dec(order.total_count),
        "total_price": fmt_dec(order.total_price),
        "express_no": order.express_no,
        "created_by_name": created_by_name,
        "approved_by_name": approved_by_name,
        "created_at": fmt_dt(order.created_at),
    }


def purchase_order_detail(
    order: PurchaseOrder,
    supplier_name: str | None = None,
    sales_order_no: str | None = None,
    warehouse_name: str | None = None,
    created_by_name: str | None = None,
    approved_by_name: str | None = None,
    items: list[dict] | None = None,
) -> dict:
    """采购单详情（列表元素 + 备注 / 关联 id / 审批时间 + 明细）。"""
    data = purchase_order_brief(
        order, supplier_name, sales_order_no, warehouse_name, created_by_name, approved_by_name
    )
    data.update(
        {
            "sales_order_id": order.sales_order_id,
            "remark": order.remark,
            "approved_at": fmt_dt(order.approved_at),
            "updated_at": fmt_dt(order.updated_at),
            "items": items or [],
        }
    )
    return data


def purchase_in_item_out(
    item: PurchaseInItem, sku: ProductSku | None = None, product: Product | None = None
) -> dict:
    """入库单明细元素。"""
    return {
        "id": item.id,
        "in_id": item.in_id,
        "order_item_id": item.order_item_id,
        "sku_id": item.sku_id,
        "sku_code": sku.sku_code if sku else None,
        "product_name": product.name if product else None,
        "spec": sku.spec if sku else None,
        "count": fmt_dec(item.count),
        "price": fmt_dec(item.price),
        "total_price": fmt_dec(item.total_price),
    }


def purchase_in_brief(
    purchase_in: PurchaseIn,
    warehouse_name: str | None = None,
    created_by_name: str | None = None,
) -> dict:
    """入库单列表元素。"""
    return {
        "id": purchase_in.id,
        "no": purchase_in.no,
        "order_id": purchase_in.order_id,
        "order_no": purchase_in.order_no,
        "status": int(purchase_in.status) if purchase_in.status is not None else 0,
        "status_text": purchase_in_status_text(purchase_in.status),
        "total_count": fmt_dec(purchase_in.total_count),
        "total_price": fmt_dec(purchase_in.total_price),
        "created_by": purchase_in.created_by,
        "created_by_name": created_by_name,
        "created_at": fmt_dt(purchase_in.created_at),
    }


def purchase_in_detail(
    purchase_in: PurchaseIn,
    warehouse_name: str | None = None,
    created_by_name: str | None = None,
    items: list[dict] | None = None,
) -> dict:
    """入库单详情（列表元素 + 备注 + 明细）。"""
    data = purchase_in_brief(purchase_in, warehouse_name, created_by_name)
    data.update(
        {
            "remark": purchase_in.remark,
            "updated_at": fmt_dt(purchase_in.updated_at),
            "items": items or [],
        }
    )
    return data

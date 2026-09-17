"""出库单相关 schema（契约 9.2 / 9.4）。

响应结构对齐契约 9.4，字段风格与 `app/schemas/serializers.py` 保持一致：
datetime 格式化、Decimal 转 float、字段名与契约示例一一对应。
"""

from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.basic import Product, ProductSku
from app.models.stock import SalesOut, SalesOutItem, sales_out_status_text
from app.schemas.serializers import fmt_dec, fmt_dt


# ---------------------------------------------------------------- 请求
class InventoryAdjustIn(BaseModel):
    """手动调整库存。quantity 是**目标值**，不是变动量。"""

    sku_id: int = Field(..., gt=0, description="SKU id")
    warehouse_id: int = Field(..., gt=0, description="仓库 id")
    quantity: Decimal = Field(..., ge=0, description="调整后的目标库存量")
    remark: str | None = Field(None, max_length=500, description="备注")


class InventoryInboundIn(BaseModel):
    """采购或提前备货入库。quantity 是本次增加量。"""

    sku_id: int = Field(..., gt=0, description="SKU id")
    warehouse_id: int = Field(..., gt=0, description="仓库 id")
    quantity: Decimal = Field(..., gt=0, description="本次入库数量")
    remark: str | None = Field(None, max_length=500, description="备注")


# ---------------------------------------------------------------- 响应
def sales_out_item_out(
    item: SalesOutItem, sku: ProductSku | None = None, product: Product | None = None
) -> dict:
    """出库单明细元素（契约 9.4 详情 items）。"""
    return {
        "id": item.id,
        "out_id": item.out_id,
        "order_item_id": item.order_item_id,
        "sku_id": item.sku_id,
        "sku_code": sku.sku_code if sku else None,
        "product_name": product.name if product else None,
        "spec": sku.spec if sku else None,
        "count": fmt_dec(item.count),
        "price": fmt_dec(item.price),
        "total_price": fmt_dec(item.total_price),
    }


def sales_out_brief(
    out: SalesOut,
    warehouse_name: str | None = None,
    created_by_name: str | None = None,
) -> dict:
    """出库单列表元素（契约 9.4 列表）。

    六阶段（契约 17.1 / 19.4）：订单删除客户字段，出库单不再返回客户名。
    """
    return {
        "id": out.id,
        "no": out.no,
        "order_id": out.order_id,
        "order_no": out.order_no,
        "warehouse_id": out.warehouse_id,
        "warehouse_name": warehouse_name,
        "status": int(out.status) if out.status is not None else 0,
        "status_text": sales_out_status_text(out.status),
        "total_count": fmt_dec(out.total_count),
        "total_price": fmt_dec(out.total_price),
        "express_no": out.express_no,
        "created_by": out.created_by,
        "created_by_name": created_by_name,
        "created_at": fmt_dt(out.created_at),
    }


def sales_out_detail(
    out: SalesOut,
    warehouse_name: str | None = None,
    created_by_name: str | None = None,
    items: list[dict] | None = None,
) -> dict:
    """出库单详情（列表元素 + 备注 + 明细）。"""
    data = sales_out_brief(out, warehouse_name, created_by_name)
    data.update(
        {
            "remark": out.remark,
            "updated_at": fmt_dt(out.updated_at),
            "items": items or [],
        }
    )
    return data

"""移库单 / 盘点单相关 schema（契约 16 / 17）。

响应结构对齐契约 16.3 / 17.3，字段风格与 `app/schemas/stock.py` 保持一致：
datetime 格式化、Decimal 转 float、字段名与契约示例一一对应。
"""

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.models.basic import Product, ProductSku
from app.models.ops import (
    StockTake,
    StockTakeItem,
    StockTransfer,
    StockTransferItem,
    stock_take_status_text,
    transfer_status_text,
)
from app.schemas.serializers import fmt_dec, fmt_dt


# ---------------------------------------------------------------- 请求
# 数量上界：数据库列是 decimal(14,2)，最大 999999999999.99。
# 不设上界的话超范围值能通过 Pydantic，落库时被 MySQL 拒绝、接口返回 500（P2）。
MAX_QUANTITY = Decimal("999999999999.99")


class TransferItemIn(BaseModel):
    """移库明细入参。"""

    sku_id: int = Field(..., gt=0, description="SKU id")
    count: Decimal = Field(..., gt=0, le=MAX_QUANTITY, description="移库数量")


class TransferCreateIn(BaseModel):
    """创建移库单。total_count 由后端按明细汇总，不接受前端传值。"""

    from_warehouse_id: int = Field(..., gt=0, description="出库仓 id")
    to_warehouse_id: int = Field(..., gt=0, description="入库仓 id")
    remark: str | None = Field(None, max_length=500, description="备注")
    items: list[TransferItemIn] = Field(..., min_length=1, description="移库明细，至少一条")

    @field_validator("items")
    @classmethod
    def check_items(cls, value: list[TransferItemIn]) -> list[TransferItemIn]:
        """明细不能为空，且同一 SKU 不允许重复行（契约 16.3 校验 3）。"""
        if not value:
            raise ValueError("移库明细不能为空")
        sku_ids = [item.sku_id for item in value]
        if len(sku_ids) != len(set(sku_ids)):
            raise ValueError("移库明细中存在重复的 SKU")
        return value


class StockTakeCreateIn(BaseModel):
    """新建盘点单。sku_ids 不传或为空 → 取该仓库所有已有库存记录的 SKU。"""

    warehouse_id: int = Field(..., gt=0, description="盘点仓库 id")
    remark: str | None = Field(None, max_length=500, description="备注")
    sku_ids: list[int] | None = Field(None, description="参与盘点的 SKU id 列表，可空")


class StockTakeItemIn(BaseModel):
    """录入实盘数量。只传部分行时，未传的行保持原值。"""

    item_id: int = Field(..., gt=0, description="盘点明细 id")
    actual_quantity: Decimal = Field(..., ge=0, le=MAX_QUANTITY, description="实盘数量")
    remark: str | None = Field(None, max_length=255, description="行备注")


class StockTakeItemsIn(BaseModel):
    """批量录入实盘数量。"""

    items: list[StockTakeItemIn] = Field(..., min_length=1, description="盘点明细，至少一条")

    @field_validator("items")
    @classmethod
    def check_items(cls, value: list[StockTakeItemIn]) -> list[StockTakeItemIn]:
        """明细不能为空，且同一盘点明细不允许重复行（契约 17.3）。"""
        if not value:
            raise ValueError("盘点明细不能为空")
        item_ids = [item.item_id for item in value]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("盘点明细中存在重复的行")
        return value


# ---------------------------------------------------------------- 响应
def transfer_item_out(
    item: StockTransferItem, sku: ProductSku | None = None, product: Product | None = None
) -> dict:
    """移库单明细元素（契约 16.3 详情 items）。"""
    return {
        "id": item.id,
        "transfer_id": item.transfer_id,
        "sku_id": item.sku_id,
        "sku_code": sku.sku_code if sku else None,
        "product_name": product.name if product else None,
        "spec": sku.spec if sku else None,
        "count": fmt_dec(item.count),
    }


def transfer_brief(
    transfer: StockTransfer,
    from_warehouse_name: str | None = None,
    to_warehouse_name: str | None = None,
    created_by_name: str | None = None,
) -> dict:
    """移库单列表元素（契约 16.3：列表元素 = 详情去掉 items）。"""
    return {
        "id": transfer.id,
        "no": transfer.no,
        "from_warehouse_id": transfer.from_warehouse_id,
        "from_warehouse_name": from_warehouse_name,
        "to_warehouse_id": transfer.to_warehouse_id,
        "to_warehouse_name": to_warehouse_name,
        "status": int(transfer.status) if transfer.status is not None else 0,
        "status_text": transfer_status_text(transfer.status),
        "total_count": fmt_dec(transfer.total_count),
        "remark": transfer.remark,
        "created_by": transfer.created_by,
        "created_by_name": created_by_name,
        "finished_at": fmt_dt(transfer.finished_at),
        "created_at": fmt_dt(transfer.created_at),
        "updated_at": fmt_dt(transfer.updated_at),
    }


def transfer_detail(
    transfer: StockTransfer,
    from_warehouse_name: str | None = None,
    to_warehouse_name: str | None = None,
    created_by_name: str | None = None,
    items: list[dict] | None = None,
) -> dict:
    """移库单详情（列表元素 + 明细）。"""
    data = transfer_brief(transfer, from_warehouse_name, to_warehouse_name, created_by_name)
    data["items"] = items or []
    return data


def stock_take_item_out(
    item: StockTakeItem, sku: ProductSku | None = None, product: Product | None = None
) -> dict:
    """盘点单明细元素（契约 17.3 详情 items）。"""
    return {
        "id": item.id,
        "stock_take_id": item.stock_take_id,
        "sku_id": item.sku_id,
        "sku_code": sku.sku_code if sku else None,
        "product_name": product.name if product else None,
        "spec": sku.spec if sku else None,
        "book_quantity": fmt_dec(item.book_quantity),
        "actual_quantity": fmt_dec(item.actual_quantity),
        "diff_quantity": fmt_dec(item.diff_quantity),
        "remark": item.remark,
    }


def stock_take_brief(
    take: StockTake,
    warehouse_name: str | None = None,
    created_by_name: str | None = None,
) -> dict:
    """盘点单列表元素（契约 17.3：列表元素 = 详情去掉 items）。"""
    return {
        "id": take.id,
        "no": take.no,
        "warehouse_id": take.warehouse_id,
        "warehouse_name": warehouse_name,
        "status": int(take.status) if take.status is not None else 0,
        "status_text": stock_take_status_text(take.status),
        "total_count": fmt_dec(take.total_count),
        "diff_count": fmt_dec(take.diff_count),
        "remark": take.remark,
        "created_by": take.created_by,
        "created_by_name": created_by_name,
        "finished_at": fmt_dt(take.finished_at),
        "created_at": fmt_dt(take.created_at),
        "updated_at": fmt_dt(take.updated_at),
    }


def stock_take_detail(
    take: StockTake,
    warehouse_name: str | None = None,
    created_by_name: str | None = None,
    items: list[dict] | None = None,
) -> dict:
    """盘点单详情（列表元素 + 明细）。"""
    data = stock_take_brief(take, warehouse_name, created_by_name)
    data["items"] = items or []
    return data

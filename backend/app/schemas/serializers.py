"""统一序列化器。

接口返回的是普通 dict（不走 response_model），由这里保证：
- datetime 统一格式化为 "YYYY-MM-DD HH:MM:SS"
- Decimal 统一转 float，前端可直接参与计算
- 字段名严格对齐《接口契约》第五节的响应示例（订单部分以 19.4 为准）
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from app.models.basic import PARTNER_TYPE_TEXT, Partner, Product, ProductSku, Warehouse
from app.models.inventory import Inventory, InventoryHistory
from app.models.order import SalesOrder, SalesOrderItem, status_text
from app.models.user import SysUser

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def fmt_dt(value: datetime | None) -> str | None:
    """时间格式化，None 原样返回。"""
    if value is None:
        return None
    return value.strftime(DATETIME_FORMAT)


def fmt_dec(value: Decimal | None) -> float:
    """Decimal 转 float，None 视为 0。"""
    if value is None:
        return 0.0
    return float(value)


def _status_int(value: Any) -> int:
    """tinyint 字段转 int。"""
    return int(value) if value is not None else 0


# ---------------------------------------------------------------- 用户 / 认证
def user_info(user: SysUser) -> dict:
    """登录接口返回的 user 结构（契约 5.1）。"""
    return {
        "id": user.id,
        "username": user.username,
        "real_name": user.real_name,
        "role": user.role,
    }


def user_out(user: SysUser) -> dict:
    """用户列表 / 详情，绝不返回 password_hash。"""
    return {
        "id": user.id,
        "username": user.username,
        "real_name": user.real_name,
        "role": user.role,
        "status": _status_int(user.status),
        "created_at": fmt_dt(user.created_at),
        "updated_at": fmt_dt(user.updated_at),
    }


# ---------------------------------------------------------------- 基础数据
def warehouse_out(warehouse: Warehouse) -> dict:
    """仓库。"""
    return {
        "id": warehouse.id,
        "code": warehouse.code,
        "name": warehouse.name,
        "address": warehouse.address,
        "status": _status_int(warehouse.status),
        "created_at": fmt_dt(warehouse.created_at),
        "updated_at": fmt_dt(warehouse.updated_at),
    }


def product_out(product: Product) -> dict:
    """商品。"""
    return {
        "id": product.id,
        "code": product.code,
        "name": product.name,
        "category": product.category,
        "unit": product.unit,
        "status": _status_int(product.status),
        "created_at": fmt_dt(product.created_at),
        "updated_at": fmt_dt(product.updated_at),
    }


def sku_out(sku: ProductSku, product: Product | None = None) -> dict:
    """SKU，附带所属商品名称。"""
    return {
        "id": sku.id,
        "product_id": sku.product_id,
        "sku_code": sku.sku_code,
        "spec": sku.spec,
        "price": fmt_dec(sku.price),
        "min_stock": fmt_dec(sku.min_stock),
        "status": _status_int(sku.status),
        "product_name": product.name if product else None,
        "created_at": fmt_dt(sku.created_at),
        "updated_at": fmt_dt(sku.updated_at),
    }


def partner_out(partner: Partner) -> dict:
    """往来单位。"""
    return {
        "id": partner.id,
        "name": partner.name,
        "type": _status_int(partner.type),
        "type_text": PARTNER_TYPE_TEXT.get(int(partner.type or 0), ""),
        "contact": partner.contact,
        "phone": partner.phone,
        "address": partner.address,
        "status": _status_int(partner.status),
        "created_at": fmt_dt(partner.created_at),
        "updated_at": fmt_dt(partner.updated_at),
    }


# ---------------------------------------------------------------- 订单
def order_item_out(item: SalesOrderItem, sku: ProductSku | None = None) -> dict:
    """订单明细（契约 19.4 详情 items 元素）。

    注意两个货号字段语义不同，不可混用：
    - `sku_code`：运营录入的货号，新品行为空；
    - `sku_code_bound`：仓库关联成功后回填的实际货号，未关联（`sku_id` 为空）时为空。
    商品名取运营录入的 `item.product_name`（自由文本），而不是系统 SKU 所属商品名。
    """
    return {
        "id": item.id,
        "product_name": item.product_name,
        "sku_code": item.sku_code,
        "is_new": _status_int(item.is_new),
        "sku_id": item.sku_id,
        "sku_code_bound": sku.sku_code if sku else None,
        "spec": sku.spec if sku else None,
        "count": fmt_dec(item.count),
        "out_count": fmt_dec(item.out_count),
        "expect_price": fmt_dec(item.expect_price),
        "total_price": fmt_dec(item.total_price),
    }


def order_brief(
    order: SalesOrder,
    created_by_name: str | None = None,
    claimed_by_name: str | None = None,
    item_count: int = 0,
    unbound_count: int = 0,
) -> dict:
    """订单列表元素（契约 19.4 列表 list 元素）。

    `item_count` 为明细行数，`unbound_count` 为 `sku_id` 为空（尚未关联货号）的行数，
    两者都由调用方批量算好后传入（详见 app/api/order.py 的 `_item_stats`）。
    """
    return {
        "id": order.id,
        "no": order.no,
        "status": _status_int(order.status),
        "status_text": status_text(order.status),
        "total_count": fmt_dec(order.total_count),
        "total_price": fmt_dec(order.total_price),
        "express_no": order.express_no,
        "created_by_name": created_by_name,
        "claimed_by_name": claimed_by_name,
        "created_at": fmt_dt(order.created_at),
        "shipped_at": fmt_dt(order.shipped_at),
        "item_count": item_count,
        "unbound_count": unbound_count,
    }


def order_detail(
    order: SalesOrder,
    created_by_name: str | None = None,
    claimed_by_name: str | None = None,
    warehouse_name: str | None = None,
    items: list[dict] | None = None,
) -> dict:
    """订单详情（列表元素 + 契约 19.4 详情追加字段）。

    `all_sku_bound` 表示是否所有明细行都已关联货号，由明细数据算出，
    仓储端据此判断能否进入「备货中」。
    """
    item_dicts = items or []
    data = order_brief(
        order,
        created_by_name=created_by_name,
        claimed_by_name=claimed_by_name,
        item_count=len(item_dicts),
        unbound_count=sum(1 for item in item_dicts if item.get("sku_id") is None),
    )
    data.update(
        {
            "remark": order.remark,
            "warehouse_id": order.warehouse_id,
            "warehouse_name": warehouse_name,
            "claimed_at": fmt_dt(order.claimed_at),
            "prepare_at": fmt_dt(order.prepare_at),
            "finished_at": fmt_dt(order.finished_at),
            "cancel_reason": order.cancel_reason,
            "all_sku_bound": all(item.get("sku_id") is not None for item in item_dicts),
            "items": item_dicts,
        }
    )
    return data


# ---------------------------------------------------------------- 库存
def inventory_out(
    inventory: Inventory,
    sku: ProductSku | None,
    product: Product | None,
    warehouse: Warehouse | None,
) -> dict:
    """库存列表元素（契约 5.5），available_quantity 由后端计算。"""
    quantity = inventory.quantity or Decimal("0")
    reserved = inventory.reserved_quantity or Decimal("0")
    return {
        "id": inventory.id,
        "sku_id": inventory.sku_id,
        "sku_code": sku.sku_code if sku else None,
        "sku_status": _status_int(sku.status) if sku else None,
        "product_name": product.name if product else None,
        "spec": sku.spec if sku else None,
        "warehouse_id": inventory.warehouse_id,
        "warehouse_name": warehouse.name if warehouse else None,
        "quantity": fmt_dec(quantity),
        "reserved_quantity": fmt_dec(reserved),
        "available_quantity": fmt_dec(quantity - reserved),
    }


def inventory_history_out(
    record: InventoryHistory,
    sku: ProductSku | None = None,
    product: Product | None = None,
    warehouse: Warehouse | None = None,
) -> dict:
    """库存流水（契约 4.9 全部字段 + 便于前端展示的关联名称）。"""
    return {
        "id": record.id,
        "sku_id": record.sku_id,
        "sku_code": sku.sku_code if sku else None,
        "product_name": product.name if product else None,
        "warehouse_id": record.warehouse_id,
        "warehouse_name": warehouse.name if warehouse else None,
        "quantity": fmt_dec(record.quantity),
        "before_quantity": fmt_dec(record.before_quantity),
        "after_quantity": fmt_dec(record.after_quantity),
        "order_no": record.order_no,
        "order_type": record.order_type,
        "created_by": record.created_by,
        "remark": record.remark,
        "created_at": fmt_dt(record.created_at),
    }

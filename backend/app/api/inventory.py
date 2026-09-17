"""库存查询与调整接口（契约 5.5 / 9.4）。

查询只读；库存调整（盘点）走统一的 `change_inventory` 服务。
"""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import BizException, normalize_page, ok, paginate
from app.core.security import require_roles
from app.models.basic import Product, ProductSku, Warehouse
from app.models.inventory import Inventory, InventoryHistory
from app.models.user import SysUser
from app.schemas.serializers import fmt_dec, inventory_history_out, inventory_out
from app.schemas.stock import InventoryAdjustIn
from app.services.inventory_service import (
    ORDER_TYPE_ADJUST,
    change_inventory,
    order_type_text,
)

router = APIRouter(prefix="/api/inventory", tags=["库存查询"])

# 数量统一保留 2 位小数，四舍五入
CENT = Decimal("0.01")


def _fmt_qty(value: Decimal) -> str:
    """数量转展示文本，去掉多余的 0（100.00 -> 100）。"""
    return format(value.normalize(), "f")


def _history_out(
    record: InventoryHistory,
    sku: ProductSku | None,
    product: Product | None,
    warehouse: Warehouse | None,
    created_by_name: str | None = None,
) -> dict:
    """库存流水序列化：在统一序列化器基础上补齐契约 9.4 的两个字段。"""
    data = inventory_history_out(record, sku, product, warehouse)
    data["order_type_text"] = order_type_text(record.order_type)
    data["created_by_name"] = created_by_name
    return data


@router.get("", summary="库存列表")
def list_inventory(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    warehouse_id: int | None = Query(None, description="按仓库筛选"),
    keyword: str | None = Query(None, description="SKU 编码 / 商品名称 / 规格"),
    db: Session = Depends(get_db),
    _current_user: SysUser = Depends(require_roles("operator", "warehouse", "admin")),
):
    """库存余额列表，available_quantity = quantity - reserved_quantity。"""
    page, page_size = normalize_page(page, page_size)

    joins = (
        select(Inventory)
        .outerjoin(ProductSku, ProductSku.id == Inventory.sku_id)
        .outerjoin(Product, Product.id == ProductSku.product_id)
        .outerjoin(Warehouse, Warehouse.id == Inventory.warehouse_id)
    )
    count_stmt = (
        select(func.count())
        .select_from(Inventory)
        .outerjoin(ProductSku, ProductSku.id == Inventory.sku_id)
        .outerjoin(Product, Product.id == ProductSku.product_id)
        .outerjoin(Warehouse, Warehouse.id == Inventory.warehouse_id)
    )

    conditions = []
    if warehouse_id is not None:
        conditions.append(Inventory.warehouse_id == warehouse_id)
    kw = (keyword or "").strip()
    if kw:
        pattern = f"%{kw}%"
        conditions.append(
            or_(
                ProductSku.sku_code.like(pattern),
                ProductSku.spec.like(pattern),
                Product.name.like(pattern),
            )
        )
    if conditions:
        joins = joins.where(*conditions)
        count_stmt = count_stmt.where(*conditions)

    total = db.scalar(count_stmt) or 0
    rows = db.execute(
        joins.add_columns(ProductSku, Product, Warehouse)
        .order_by(Inventory.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        inventory_out(inventory, sku, product, warehouse)
        for inventory, sku, product, warehouse in rows
    ]
    return ok(paginate(items, total, page, page_size))


@router.get("/alerts", summary="库存预警（安全库存）")
def list_inventory_alerts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    warehouse_id: int | None = Query(None, description="按仓库筛选"),
    db: Session = Depends(get_db),
    _current_user: SysUser = Depends(require_roles("operator", "warehouse", "admin")),
):
    """库存预警：SKU 设了安全库存（min_stock > 0）且可用量低于安全库存。

    available_quantity = quantity - reserved_quantity，短缺量 = min_stock - available_quantity（恒 > 0），
    按短缺量从大到小排序。只读接口，不产生任何库存变更。
    """
    page, page_size = normalize_page(page, page_size)

    available = Inventory.quantity - Inventory.reserved_quantity
    shortage = ProductSku.min_stock - available
    conditions = [ProductSku.min_stock > 0, available < ProductSku.min_stock]
    if warehouse_id is not None:
        conditions.append(Inventory.warehouse_id == warehouse_id)

    joins = (
        select(Inventory)
        .join(ProductSku, ProductSku.id == Inventory.sku_id)
        .outerjoin(Product, Product.id == ProductSku.product_id)
        .outerjoin(Warehouse, Warehouse.id == Inventory.warehouse_id)
    )
    count_stmt = (
        select(func.count())
        .select_from(Inventory)
        .join(ProductSku, ProductSku.id == Inventory.sku_id)
        .where(*conditions)
    )

    total = db.scalar(count_stmt) or 0
    rows = db.execute(
        joins.where(*conditions)
        .add_columns(ProductSku, Product, Warehouse)
        .order_by(shortage.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []
    for inventory, sku, product, warehouse in rows:
        data = inventory_out(inventory, sku, product, warehouse)
        available_qty = (inventory.quantity or Decimal("0")) - (
            inventory.reserved_quantity or Decimal("0")
        )
        min_stock = sku.min_stock or Decimal("0")
        data["min_stock"] = fmt_dec(min_stock)
        data["shortage"] = fmt_dec(min_stock - available_qty)
        items.append(data)
    return ok(paginate(items, total, page, page_size))


@router.get("/history", summary="库存流水")
def list_inventory_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1),
    sku_id: int | None = Query(None, description="按 SKU 筛选"),
    warehouse_id: int | None = Query(None, description="按仓库筛选"),
    db: Session = Depends(get_db),
    _current_user: SysUser = Depends(require_roles("operator", "warehouse", "admin")),
):
    """库存流水列表。"""
    page, page_size = normalize_page(page, page_size)

    conditions = []
    if sku_id is not None:
        conditions.append(InventoryHistory.sku_id == sku_id)
    if warehouse_id is not None:
        conditions.append(InventoryHistory.warehouse_id == warehouse_id)

    total = db.scalar(
        select(func.count()).select_from(InventoryHistory).where(*conditions)
    ) or 0
    rows = db.scalars(
        select(InventoryHistory)
        .where(*conditions)
        .order_by(InventoryHistory.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    # 批量取关联名称
    sku_ids = {r.sku_id for r in rows if r.sku_id}
    warehouse_ids = {r.warehouse_id for r in rows if r.warehouse_id}
    user_ids = {r.created_by for r in rows if r.created_by}
    skus = (
        {s.id: s for s in db.scalars(select(ProductSku).where(ProductSku.id.in_(sku_ids)))}
        if sku_ids
        else {}
    )
    product_ids = {s.product_id for s in skus.values()}
    products = (
        {p.id: p for p in db.scalars(select(Product).where(Product.id.in_(product_ids)))}
        if product_ids
        else {}
    )
    warehouses = (
        {w.id: w for w in db.scalars(select(Warehouse).where(Warehouse.id.in_(warehouse_ids)))}
        if warehouse_ids
        else {}
    )
    users = (
        {
            u.id: (u.real_name or u.username)
            for u in db.scalars(select(SysUser).where(SysUser.id.in_(user_ids)))
        }
        if user_ids
        else {}
    )

    items = [
        _history_out(
            record,
            skus.get(record.sku_id),
            products.get(skus[record.sku_id].product_id) if record.sku_id in skus else None,
            warehouses.get(record.warehouse_id),
            users.get(record.created_by),
        )
        for record in rows
    ]
    return ok(paginate(items, total, page, page_size))


@router.post("/adjust", summary="手动调整库存（盘点）")
def adjust_inventory(
    payload: InventoryAdjustIn,
    db: Session = Depends(get_db),
    current_user: SysUser = Depends(require_roles("admin")),
):
    """admin 专属：`quantity` 是目标值，后端算出差异后走 change_inventory。"""
    sku = db.get(ProductSku, payload.sku_id)
    if sku is None:
        raise BizException("SKU 不存在")
    warehouse = db.get(Warehouse, payload.warehouse_id)
    if warehouse is None:
        raise BizException("仓库不存在")

    inventory = db.scalar(
        select(Inventory).where(
            Inventory.sku_id == payload.sku_id,
            Inventory.warehouse_id == payload.warehouse_id,
        )
    )
    before = Decimal(inventory.quantity or 0) if inventory is not None else Decimal("0.00")
    target = Decimal(payload.quantity).quantize(CENT, rounding=ROUND_HALF_UP)
    diff = target - before

    if diff != 0:
        change_inventory(
            db,
            [
                {
                    "sku_id": payload.sku_id,
                    "warehouse_id": payload.warehouse_id,
                    "quantity": diff,
                }
            ],
            # 调整单没有业务单号，用时间戳生成一个便于追溯的编号
            "ADJ" + datetime.now().strftime("%Y%m%d%H%M%S"),
            ORDER_TYPE_ADJUST,
            current_user.id,
            # 盘点备注写入库存流水，保证调整有据可查（契约 9.4）
            remark=payload.remark,
        )
        db.commit()
        # 库存行可能是刚才由 change_inventory 懒创建的，重新查一次拿到最新值
        inventory = db.scalar(
            select(Inventory).where(
                Inventory.sku_id == payload.sku_id,
                Inventory.warehouse_id == payload.warehouse_id,
            )
        )

    product = db.get(Product, sku.product_id) if sku.product_id else None
    data = inventory_out(inventory, sku, product, warehouse) if inventory is not None else None
    return ok(
        data,
        msg=(
            f"库存已调整：{sku.sku_code} 在{warehouse.name} "
            f"由 {_fmt_qty(before)} 变为 {_fmt_qty(target)}"
        ),
    )
